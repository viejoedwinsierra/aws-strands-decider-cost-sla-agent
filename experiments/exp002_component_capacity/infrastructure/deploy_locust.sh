#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
LOCUST_FILE="${SCRIPT_DIR}/../scripts/locustfile.py"
VALIDATOR_FILE="${SCRIPT_DIR}/../scripts/verify_locked_environment.py"

[[ -f "$CONFIG_FILE" ]] || { echo "Missing config: $CONFIG_FILE" >&2; exit 1; }
[[ -f "$LOCUST_FILE" ]] || { echo "Missing locustfile: $LOCUST_FILE" >&2; exit 1; }
[[ -f "$VALIDATOR_FILE" ]] || { echo "Missing validator: $VALIDATOR_FILE" >&2; exit 1; }

set -a
source "$CONFIG_FILE"
set +a

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
: "${LOCUST_INSTANCE_ID:?}" "${EVIDENCE_BUCKET:?}" "${LOCUST_BUNDLE_HASH:?}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

VALIDATOR_FILE="$VALIDATOR_FILE" LOCUST_BUNDLE_HASH="$LOCUST_BUNDLE_HASH" LOCUST_FILE="$LOCUST_FILE" EVIDENCE_BUCKET="$EVIDENCE_BUCKET" python3 - "$TMP" <<'PYCODE'
import base64
import json
import os
from pathlib import Path
import sys

source = Path(os.environ["LOCUST_FILE"]).read_bytes()
payload = base64.b64encode(source).decode("ascii")
bucket = os.environ["EVIDENCE_BUCKET"]
bundle_hash = os.environ["LOCUST_BUNDLE_HASH"]
if len(bundle_hash) != 64 or any(c not in "0123456789abcdef" for c in bundle_hash):
    raise SystemExit("ERROR: Invalid LOCUST_BUNDLE_HASH")
validator_payload = base64.b64encode(Path(os.environ["VALIDATOR_FILE"]).read_bytes()).decode("ascii")

cmd = f"""set -eu
APP_DIR=/opt/exp002-locust
VENV_DIR="$APP_DIR/venvs/{bundle_hash}"
WHEEL_DIR="$APP_DIR/wheels311/{bundle_hash}"
EVIDENCE_DIR=/var/lib/exp002-evidence/locust/{bundle_hash}
mkdir -p "$APP_DIR" "$WHEEL_DIR" "$EVIDENCE_DIR"
printf %s '{payload}' | base64 -d > "$APP_DIR/locustfile.py.next"
python3 -m py_compile "$APP_DIR/locustfile.py.next"
mv "$APP_DIR/locustfile.py.next" "$APP_DIR/locustfile.py"
printf %s '{validator_payload}' | base64 -d > "$APP_DIR/verify_locked_environment.py"
if [ ! -x "$VENV_DIR/bin/python" ] || [ ! -f "$VENV_DIR/.install-complete" ]; then
  dnf install -y python3.11 python3.11-pip
  rm -rf "$VENV_DIR"
  python3.11 -m venv "$VENV_DIR"
fi
aws s3 sync \
  s3://{bucket}/dependencies/exp002/locust/python311-linux-x86_64/{bundle_hash}/ \
  "$WHEEL_DIR/" --delete
test -s "$WHEEL_DIR/SHA256SUMS.txt"
test -s "$WHEEL_DIR/requirements.lock"
ACTUAL_HASH="$(sha256sum "$WHEEL_DIR/SHA256SUMS.txt" | cut -d ' ' -f 1)"
test "$ACTUAL_HASH" = "{bundle_hash}"
(cd "$WHEEL_DIR"; sha256sum -c SHA256SUMS.txt)
rm -f "$VENV_DIR/.install-complete"
"$VENV_DIR/bin/python" -m pip install --no-index --find-links="$WHEEL_DIR" -r "$WHEEL_DIR/requirements.lock"
"$VENV_DIR/bin/python" -m pip check
"$VENV_DIR/bin/python" "$APP_DIR/verify_locked_environment.py" "$WHEEL_DIR/requirements.lock" > "$EVIDENCE_DIR/lock_verification.json"
"$VENV_DIR/bin/python" -m pip freeze > "$EVIDENCE_DIR/pip_freeze.txt"
cp "$WHEEL_DIR/requirements.lock" "$EVIDENCE_DIR/requirements.lock"
cp "$WHEEL_DIR/SHA256SUMS.txt" "$EVIDENCE_DIR/SHA256SUMS.txt"
"$VENV_DIR/bin/locust" --version
printf '%s\\n' '{bundle_hash}' > "$VENV_DIR/.install-complete"
echo 'EXP-002 Locust deployment successful'
"""

Path(sys.argv[1]).write_text(json.dumps({"commands": [cmd]}))
PYCODE

echo "EXP-002 | Locust deploy | $LOCUST_INSTANCE_ID"

COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$LOCUST_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment 'EXP-002 idempotent Locust deployment' \
  --parameters "file://$TMP" \
  --query Command.CommandId \
  --output text)"

if ! aws_cli ssm wait command-executed \
  --command-id "$COMMAND_ID" \
  --instance-id "$LOCUST_INSTANCE_ID"; then
  echo "SSM waiter finished without Success; inspecting result..." >&2
fi

aws_cli ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$LOCUST_INSTANCE_ID" \
  --query '{Status:Status,Output:StandardOutputContent,Errors:StandardErrorContent}' \
  --output json

STATUS="$(aws_cli ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$LOCUST_INSTANCE_ID" \
  --query Status \
  --output text)"

[[ "$STATUS" == "Success" ]] || exit 1
