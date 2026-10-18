#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
INSTANCE_ID='' APP_NAME='' PORT=''
usage() { echo "Usage: $0 --instance-id i-... --app-name name --port 8001 [--profile profile] [--region region] [--run-id ID]"; }
while (($#)); do
  (($# >= 2)) || { usage >&2; exit 2; }
  case "$1" in
    --instance-id) INSTANCE_ID="$2";;
    --app-name) APP_NAME="$2";;
    --port) PORT="$2";;
    --profile) AWS_PROFILE="$2";;
    --region) AWS_REGION="$2";;
    --run-id) RUN_ID="$2";;
    *) usage >&2; exit 2;;
  esac
  shift 2
done
[[ "$INSTANCE_ID" =~ ^i-[0-9a-f]{8,17}$ ]] || { echo 'Invalid instance ID' >&2; exit 2; }
[[ "$APP_NAME" =~ ^[a-z][a-z0-9-]{0,39}$ ]] || { echo 'Invalid app name' >&2; exit 2; }
[[ "$PORT" =~ ^[0-9]{4,5}$ ]] && ((10#$PORT >= 1024 && 10#$PORT <= 65535)) || { echo 'Invalid port' >&2; exit 2; }
[[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid run ID' >&2; exit 2; }
[[ -f "$ROOT/app/main.py" ]] || { echo 'Missing app/main.py' >&2; exit 1; }
for cmd in aws python3; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }; done
aws_cli() { aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }
OUT="${EVIDENCE_ROOT:-$HOME/aws-cost-sla-evidence}/EXP-002/$RUN_ID/deployments/$APP_NAME"
mkdir -p "$OUT"
PARAMS="$(mktemp)"; trap 'rm -f "$PARAMS"' EXIT
python3 - "$PARAMS" "$ROOT/app/main.py" "$APP_NAME" "$PORT" "$RUN_ID" "$INSTANCE_ID" <<'PY'
import base64,json,pathlib,sys
out,source,name,port,run,instance=sys.argv[1:]
code=base64.b64encode(pathlib.Path(source).read_bytes()).decode()
cmd=r'''set -eu
APP_NAME='__NAME__'
PORT='__PORT__'
RUN_ID='__RUN__'
APP_DIR="/opt/exp002/apps/$APP_NAME"
UNIT="exp002-$APP_NAME.service"
E="/var/lib/exp002-evidence/$RUN_ID/fastapi/$APP_NAME"
mkdir -p "$E"
# Reject replacement; a new run must not silently alter an existing deployment.
if [ -e "$APP_DIR" ] || [ -e "/etc/systemd/system/$UNIT" ]; then
  echo "ERROR: application already exists: $APP_NAME" >&2; exit 1
fi
if ! systemctl is-active --quiet postgresql; then
  echo 'ERROR: PostgreSQL must remain active for LB-03' >&2; exit 1
fi
if ss -ltnH "( sport = :$PORT )" | grep -q .; then
  echo "ERROR: TCP port $PORT is already listening" >&2; exit 1
fi
python3 --version > "$E/python_version.txt" 2>&1
# Amazon Linux 2023 may have venv without ensurepip/pip.
if ! python3 -m ensurepip --version >/dev/null 2>&1; then
  echo 'Installing python3-pip prerequisite with dnf' | tee "$E/prerequisite_action.txt"
  dnf install -y python3-pip > "$E/dnf_python3_pip.log" 2>&1
fi
mkdir -p "$APP_DIR"
python3 -m venv "$APP_DIR/.venv"
if ! "$APP_DIR/.venv/bin/python" -m pip --version > "$E/venv_pip_version.txt" 2>&1; then
  echo 'ERROR: venv has no pip after prerequisite setup' >&2; exit 1
fi
python3 - <<'REMOTE_PY'
import base64,pathlib
pathlib.Path('/opt/exp002/apps/__NAME__/main.py').write_bytes(base64.b64decode('__CODE__'))
REMOTE_PY
"$APP_DIR/.venv/bin/python" -m pip install --disable-pip-version-check 'fastapi==0.115.6' 'uvicorn==0.34.0' > "$E/pip_install.log" 2>&1
"$APP_DIR/.venv/bin/python" -m pip freeze > "$E/pip_freeze.txt"
cat > "/etc/systemd/system/$UNIT" <<SERVICE
[Unit]
Description=EXP-002 FastAPI $APP_NAME
After=network.target postgresql.service
Requires=postgresql.service
[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port $PORT --workers 1
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable --now "$UNIT" > "$E/systemd_enable.txt" 2>&1
python3 - <<'HEALTH'
import json,time,urllib.request
for attempt in range(20):
    try:
        with urllib.request.urlopen('http://127.0.0.1:__PORT__/health',timeout=2) as response:
            result=json.load(response)
        assert result == {'status':'ok','mode':'standalone'}, result
        print('HEALTH_OK='+json.dumps(result)); break
    except Exception:
        if attempt==19: raise
        time.sleep(1)
HEALTH
systemctl is-active "$UNIT" > "$E/systemd_status.txt"
systemctl is-active postgresql > "$E/postgresql_status.txt"
ss -ltn > "$E/listening_ports.txt"
printf '{"schema_version":"1.0","experiment_id":"EXP-002","stage":"LB-03","run_id":"%s","instance_id":"__INSTANCE__","component_id":"%s","mode":"standalone","port":%s}\n' "$RUN_ID" "$APP_NAME" "$PORT" > "$E/manifest.json"
echo "EVIDENCE_DIR=$E"
'''
for key,value in [('__NAME__',name),('__PORT__',port),('__RUN__',run),('__INSTANCE__',instance),('__CODE__',code)]:
    cmd=cmd.replace(key,value)
pathlib.Path(out).write_text(json.dumps({'commands':[cmd]}))
PY
CID="$(aws_cli ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript --comment "EXP-002 LB-03 FastAPI $APP_NAME" --parameters "file://$PARAMS" --query Command.CommandId --output text)"
printf '%s\n' "$CID" > "$OUT/ssm_command_id.txt"
aws_cli ssm wait command-executed --command-id "$CID" --instance-id "$INSTANCE_ID" || true
aws_cli ssm get-command-invocation --command-id "$CID" --instance-id "$INSTANCE_ID" --output json > "$OUT/ssm_invocation.json"
python3 - "$OUT" "$INSTANCE_ID" "$RUN_ID" "$APP_NAME" "$PORT" <<'PY'
import json,pathlib,sys
out=pathlib.Path(sys.argv[1]); inv=json.loads((out/'ssm_invocation.json').read_text())
(out/'stdout.txt').write_text(inv.get('StandardOutputContent') or '')
(out/'stderr.txt').write_text(inv.get('StandardErrorContent') or '')
manifest={'schema_version':'1.0','experiment_id':'EXP-002','stage':'LB-03','run_id':sys.argv[3], 'instance_id':sys.argv[2], 'component_id':sys.argv[4], 'port':int(sys.argv[5]), 'mode':'standalone','ssm_command_id':inv.get('CommandId'),'status':inv.get('Status')}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Status:',inv.get('Status'),'Evidence:',out)
print('STDOUT:',(out/'stdout.txt').read_text())
if inv.get('Status')!='Success':
 print('STDERR:',(out/'stderr.txt').read_text()); raise SystemExit(1)
PY
