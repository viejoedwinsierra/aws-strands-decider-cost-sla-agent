#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config/experiment.env"
APP_FILE="$SCRIPT_DIR/../exp002_fastapi/app/main.py"
VALIDATOR_FILE="$SCRIPT_DIR/../scripts/verify_locked_environment.py"

[[ -f "$CONFIG_FILE" ]] || { echo "ERROR: Missing experiment.env" >&2; exit 1; }
[[ -f "$APP_FILE" ]] || { echo "ERROR: Missing FastAPI main.py" >&2; exit 1; }
[[ -f "$VALIDATOR_FILE" ]] || { echo "ERROR: Missing lock validator" >&2; exit 1; }

set -a
source "$CONFIG_FILE"
set +a

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"

: "${WORKLOAD_INSTANCE_ID:?Missing WORKLOAD_INSTANCE_ID}"
: "${EVIDENCE_BUCKET:?Missing EVIDENCE_BUCKET}"
: "${FASTAPI_BUNDLE_HASH:?Missing FASTAPI_BUNDLE_HASH}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

VALIDATOR_FILE="$VALIDATOR_FILE" APP_FILE="$APP_FILE" EVIDENCE_BUCKET="$EVIDENCE_BUCKET" FASTAPI_BUNDLE_HASH="$FASTAPI_BUNDLE_HASH" RUN_ID="$RUN_ID" \
python3 - "$TMP" <<'PYCODE'
import base64
import json
import os
import sys
from pathlib import Path

source = Path(os.environ["APP_FILE"]).read_bytes()
payload = base64.b64encode(source).decode("ascii")
validator_payload = base64.b64encode(Path(os.environ["VALIDATOR_FILE"]).read_bytes()).decode("ascii")
bucket = os.environ["EVIDENCE_BUCKET"]
bundle_hash = os.environ["FASTAPI_BUNDLE_HASH"]
if len(bundle_hash) != 64 or any(c not in "0123456789abcdef" for c in bundle_hash):
    raise SystemExit("ERROR: Invalid FASTAPI_BUNDLE_HASH")
run_id = os.environ["RUN_ID"]

cmd = f"""set -eu

APP_DIR=/opt/exp002-fastapi
UNIT=exp002-fastapi.service
EVIDENCE_DIR=/var/lib/exp002-evidence/{run_id}/fastapi

mkdir -p "$APP_DIR" "$EVIDENCE_DIR"

printf %s '{payload}' | base64 -d > "$APP_DIR/main.py.next"
mv "$APP_DIR/main.py.next" "$APP_DIR/main.py"
printf %s '{validator_payload}' | base64 -d > "$APP_DIR/verify_locked_environment.py"

VENV_DIR="$APP_DIR/venvs/{bundle_hash}"

if [ ! -x "$VENV_DIR/bin/python" ] || [ ! -f "$VENV_DIR/.install-complete" ]; then
  dnf install -y python3.11 python3.11-pip
  rm -rf "$VENV_DIR"
  python3.11 -m venv "$VENV_DIR"
fi

WHEEL_DIR="$APP_DIR/wheels311/{bundle_hash}"
mkdir -p "$WHEEL_DIR"

aws s3 sync \
  s3://{bucket}/dependencies/exp002/fastapi/python311-linux-x86_64/{bundle_hash}/ \
  "$WHEEL_DIR/" \
  --delete

test -s "$WHEEL_DIR/SHA256SUMS.txt"

ACTUAL_HASH="$(sha256sum "$WHEEL_DIR/SHA256SUMS.txt" | cut -d ' ' -f 1)"
test "$ACTUAL_HASH" = "{bundle_hash}"

(
  cd "$WHEEL_DIR"
  sha256sum -c SHA256SUMS.txt
)

rm -f "$VENV_DIR/.install-complete"

"$VENV_DIR/bin/python" -m pip install \
  --no-index \
  --find-links="$WHEEL_DIR" \
  -r "$WHEEL_DIR/requirements.lock"

"$VENV_DIR/bin/python" -m pip check
"$VENV_DIR/bin/python" "$APP_DIR/verify_locked_environment.py" "$WHEEL_DIR/requirements.lock" > "$EVIDENCE_DIR/lock_verification.json"
cp "$WHEEL_DIR/requirements.lock" "$EVIDENCE_DIR/requirements.lock"
cp "$WHEEL_DIR/SHA256SUMS.txt" "$EVIDENCE_DIR/SHA256SUMS.txt"
"$VENV_DIR/bin/python" -m pip freeze > "$EVIDENCE_DIR/pip_freeze.txt"
printf '%s\\n' '{bundle_hash}' > "$VENV_DIR/.install-complete"

cat > "/etc/systemd/system/$UNIT" <<SERVICE
[Unit]
Description=EXP-002 FastAPI workload
After=network.target postgresql.service\nRequires=postgresql.service

[Service]
Type=simple
User=exp002_api
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1
Restart=on-failure
RestartSec=3
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "$UNIT"
systemctl restart "$UNIT"

python3.11 - <<'HEALTH'
import json
import time
import urllib.request

for attempt in range(30):
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8001/health", timeout=2
        ) as response:
            result = json.load(response)

        assert result == {{"status": "ok", "mode": "postgresql"}}, result
        print("HEALTH_OK=" + json.dumps(result))
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
HEALTH

curl --fail --silent --show-error http://127.0.0.1:8001/ready > "$EVIDENCE_DIR/readiness.json"
systemctl is-active "$UNIT" > "$EVIDENCE_DIR/systemd_status.txt"
ss -ltn > "$EVIDENCE_DIR/listening_ports.txt"

echo "EXP-002 FastAPI deployment successful"
"""

Path(sys.argv[1]).write_text(json.dumps({"commands": [cmd]}))
PYCODE

echo "EXP-002 | Deploy FastAPI | $WORKLOAD_INSTANCE_ID"

COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$WORKLOAD_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "EXP-002 FastAPI deployment" \
  --parameters "file://$TMP" \
  --query Command.CommandId \
  --output text)"

if ! aws_cli ssm wait command-executed \
  --command-id "$COMMAND_ID" \
  --instance-id "$WORKLOAD_INSTANCE_ID"; then
  echo "SSM waiter finished; inspecting result..." >&2
fi

aws_cli ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$WORKLOAD_INSTANCE_ID" \
  --query '{Status:Status,Output:StandardOutputContent,Errors:StandardErrorContent}' \
  --output json

STATUS="$(aws_cli ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$WORKLOAD_INSTANCE_ID" \
  --query Status \
  --output text)"

[[ "$STATUS" == "Success" ]] || exit 1

echo "EXP-002 | FastAPI deployment completed"
