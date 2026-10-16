#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
LOCUST_FILE="${SCRIPT_DIR}/../scripts/locustfile.py"

[[ -f "$CONFIG_FILE" ]] || { echo "Missing config: $CONFIG_FILE" >&2; exit 1; }
[[ -f "$LOCUST_FILE" ]] || { echo "Missing locustfile: $LOCUST_FILE" >&2; exit 1; }

set -a
source "$CONFIG_FILE"
set +a

: "${AWS_PROFILE:?}" "${AWS_REGION:?}" "${LOCUST_INSTANCE_ID:?}" "${EVIDENCE_BUCKET:?}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

LOCUST_FILE="$LOCUST_FILE" EVIDENCE_BUCKET="$EVIDENCE_BUCKET" python3 - "$TMP" <<'PYCODE'
import base64
import json
import os
from pathlib import Path
import sys

source = Path(os.environ["LOCUST_FILE"]).read_bytes()
payload = base64.b64encode(source).decode("ascii")
bucket = os.environ["EVIDENCE_BUCKET"]

cmd = f"""set -eu
mkdir -p /opt/exp001-locust
printf %s {payload} | base64 -d > /opt/exp001-locust/locustfile.py.next

python3 -m py_compile /opt/exp001-locust/locustfile.py.next

if ! cmp -s /opt/exp001-locust/locustfile.py.next /opt/exp001-locust/locustfile.py; then
  mv /opt/exp001-locust/locustfile.py.next /opt/exp001-locust/locustfile.py
  echo 'Locust workload updated'
else
  rm -f /opt/exp001-locust/locustfile.py.next
  echo 'Locust workload unchanged'
fi

if [ ! -x /opt/exp001-locust/venv311/bin/locust ]; then
  dnf install -y python3.11 python3.11-pip
  python3.11 -m venv /opt/exp001-locust/venv311
fi

mkdir -p /opt/exp001-locust/wheels311

aws s3 sync \
  s3://{bucket}/dependencies/locust/python311-linux-x86_64/ \
  /opt/exp001-locust/wheels311/

# Instalación estrictamente offline: no consulta PyPI.
# También permite corregir dependencias incompletas en ejecuciones anteriores.
/opt/exp001-locust/venv311/bin/python -m pip install \
  --no-index \
  --find-links=/opt/exp001-locust/wheels311 \
  'locust==2.46.7' \
  'typing-extensions>=4.6.0'

/opt/exp001-locust/venv311/bin/python -m pip check
/opt/exp001-locust/venv311/bin/locust --version
"""

Path(sys.argv[1]).write_text(json.dumps({"commands": [cmd]}))
PYCODE

echo "EXP-001 | Locust deploy | $LOCUST_INSTANCE_ID"

COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$LOCUST_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment 'EXP-001 idempotent Locust deployment' \
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
