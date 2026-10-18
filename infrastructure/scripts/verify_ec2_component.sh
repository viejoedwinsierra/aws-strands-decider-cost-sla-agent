#!/usr/bin/env bash
set -Eeuo pipefail
usage(){ echo "Usage: $0 --instance-id i-... --component host|postgresql|fastapi [--app-name name --port 8001] [--stage LB-03] [--run-id ID] [--profile name] [--region region]"; }
INSTANCE_ID='' COMPONENT='' APP_NAME='' PORT='' STAGE='preflight'
AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}" AWS_REGION="${AWS_REGION:-us-east-1}" RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
while (($#)); do
  (($#>=2)) || { usage >&2; exit 2; }
  case "$1" in
    --instance-id) INSTANCE_ID="$2";; --component) COMPONENT="$2";; --app-name) APP_NAME="$2";; --port) PORT="$2";; --stage) STAGE="$2";; --run-id) RUN_ID="$2";; --profile) AWS_PROFILE="$2";; --region) AWS_REGION="$2";; *) usage >&2; exit 2;;
  esac
  shift 2
done
[[ "$INSTANCE_ID" =~ ^i-[0-9a-f]{8,17}$ && "$COMPONENT" =~ ^(host|postgresql|fastapi)$ && "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ && "$STAGE" =~ ^[a-zA-Z0-9_-]+$ ]] || { usage >&2; exit 2; }
if [[ "$COMPONENT" == fastapi ]]; then
  [[ "$APP_NAME" =~ ^[a-z][a-z0-9-]{0,39}$ && "$PORT" =~ ^[0-9]{4,5}$ ]] && ((10#$PORT>=1024 && 10#$PORT<=65535)) || { usage >&2; exit 2; }
fi
for x in aws python3; do command -v "$x" >/dev/null || { echo "Missing $x" >&2; exit 1; }; done
aws_cli(){ aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }
OUT="${EVIDENCE_ROOT:-$HOME/aws-cost-sla-evidence}/EXP-002/$RUN_ID/verification/$COMPONENT${APP_NAME:+-$APP_NAME}"
mkdir -p "$OUT"
aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" --output json > "$OUT/ec2_description.json"
STATE="$(python3 - "$OUT/ec2_description.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); print(x['Reservations'][0]['Instances'][0]['State']['Name'])
PY
)"
[[ "$STATE" == running ]] || { echo "EC2 state: $STATE" >&2; exit 1; }
aws_cli ssm describe-instance-information --filters "Key=InstanceIds,Values=$INSTANCE_ID" --output json > "$OUT/ssm_instance_information.json"
python3 - "$OUT/ssm_instance_information.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))['InstanceInformationList']; assert x and x[0]['PingStatus']=='Online', 'SSM is not Online'
PY
PARAMS="$(mktemp)"; trap 'rm -f "$PARAMS"' EXIT
python3 - "$PARAMS" "$COMPONENT" "$APP_NAME" "$PORT" <<'PY'
import json,sys
path,component,name,port=sys.argv[1:]
cmd=['set -eu','echo "timestamp_utc=$(date -u +%FT%TZ)"','python3 --version','python3 -m pip --version || true','python3 -m venv --help >/dev/null 2>&1 && echo VENV_AVAILABLE || echo VENV_UNAVAILABLE','free -b','df -B1 /','ss -ltn']
if component=='postgresql': cmd += ['systemctl is-active postgresql','runuser -u postgres -- psql -X -At -c "SELECT 1"']
if component=='fastapi': cmd += [f'systemctl is-active exp002-{name}.service',f'curl -fsS --max-time 5 http://127.0.0.1:{port}/health']
open(path,'w').write(json.dumps({'commands':cmd}))
PY
CID="$(aws_cli ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript --parameters "file://$PARAMS" --comment "EXP-002 verify $COMPONENT" --query Command.CommandId --output text)"
printf '%s\n' "$CID" > "$OUT/ssm_command_id.txt"
aws_cli ssm wait command-executed --command-id "$CID" --instance-id "$INSTANCE_ID" || true
aws_cli ssm get-command-invocation --command-id "$CID" --instance-id "$INSTANCE_ID" --output json > "$OUT/ssm_invocation.json"
python3 - "$OUT" "$RUN_ID" "$STAGE" "$COMPONENT" "$INSTANCE_ID" "$APP_NAME" "$PORT" <<'PY'
import json,sys,pathlib,datetime
out=pathlib.Path(sys.argv[1]); inv=json.loads((out/'ssm_invocation.json').read_text())
(out/'stdout.txt').write_text(inv.get('StandardOutputContent') or '')
(out/'stderr.txt').write_text(inv.get('StandardErrorContent') or '')
manifest=dict(schema_version='1.0',experiment_id='EXP-002',run_id=sys.argv[2],stage=sys.argv[3],component_id=sys.argv[4],instance_id=sys.argv[5],app_name=sys.argv[6] or None,port=int(sys.argv[7]) if sys.argv[7] else None,ssm_command_id=inv.get('CommandId'),status=inv.get('Status'),collected_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Status:',inv.get('Status'),'Evidence:',out)
print((out/'stdout.txt').read_text())
if inv.get('Status')!='Success':
 print((out/'stderr.txt').read_text(),file=sys.stderr); sys.exit(1)
PY
