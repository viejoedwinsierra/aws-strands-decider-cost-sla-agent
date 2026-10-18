#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

[[ -f "$CONFIG_FILE" ]] || {
  echo "ERROR: Missing experiment.env" >&2
  exit 1
}

set -a
source "$CONFIG_FILE"
set +a

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

: "${WORKLOAD_INSTANCE_ID:?Missing WORKLOAD_INSTANCE_ID}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

echo "EXP-002 | Verify workload | $WORKLOAD_INSTANCE_ID"

STATE="$(aws_cli ec2 describe-instances \
  --instance-ids "$WORKLOAD_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text)"

[[ "$STATE" == "running" ]] || {
  echo "ERROR: EC2 not running: $STATE" >&2
  exit 1
}

PING="$(aws_cli ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=$WORKLOAD_INSTANCE_ID" \
  --query 'InstanceInformationList[0].PingStatus' \
  --output text)"

[[ "$PING" == "Online" ]] || {
  echo "ERROR: SSM not Online: $PING" >&2
  exit 1
}

REMOTE_CHECK='set -e
systemctl is-active --quiet postgresql
systemctl is-active --quiet exp002-fastapi
curl -fsS --max-time 10 http://127.0.0.1:8001/health
'

PARAMETERS="$(REMOTE_CHECK="$REMOTE_CHECK" python3 - <<'PY'
import json
import os
print(json.dumps({"commands": [os.environ["REMOTE_CHECK"]]}))
PY
)"

COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$WORKLOAD_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters "$PARAMETERS" \
  --query 'Command.CommandId' \
  --output text)"

aws_cli ssm wait command-executed \
  --command-id "$COMMAND_ID" \
  --instance-id "$WORKLOAD_INSTANCE_ID"

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

[[ "$STATUS" == "Success" ]] || {
  echo "ERROR: Workload verification failed: $STATUS" >&2
  exit 1
}

echo "EXP-002 | Workload verification PASSED"
