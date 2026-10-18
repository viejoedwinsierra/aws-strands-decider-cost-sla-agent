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

: "${WORKLOAD_INSTANCE_ID:?}"
: "${LOCUST_INSTANCE_ID:?}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

WORKLOAD_PRIVATE_IP="$(aws_cli ec2 describe-instances \
  --instance-ids "$WORKLOAD_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' \
  --output text)"

[[ "$WORKLOAD_PRIVATE_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "ERROR: Invalid workload private IP" >&2
  exit 1
}

echo "EXP-002 | Verify private connectivity"
echo "Source: $LOCUST_INSTANCE_ID"
echo "Target: http://$WORKLOAD_PRIVATE_IP:8001/health"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

python3 - "$TMP" "$WORKLOAD_PRIVATE_IP" <<'PY'
import json
import sys
from pathlib import Path

destination = Path(sys.argv[1])
ip = sys.argv[2]

commands = [
    "set -eu",
    f"curl --fail --silent --show-error --connect-timeout 5 --max-time 15 "
    f"http://{ip}:8001/health",
    "echo",
    "echo NETWORK_VERIFICATION_PASSED",
]

destination.write_text(json.dumps({"commands": commands}))
PY

COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$LOCUST_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "EXP-002 private network verification" \
  --parameters "file://$TMP" \
  --query Command.CommandId \
  --output text)"

if ! aws_cli ssm wait command-executed \
  --command-id "$COMMAND_ID" \
  --instance-id "$LOCUST_INSTANCE_ID"; then
  echo "SSM verification did not finish successfully." >&2
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

[[ "$STATUS" == "Success" ]] || {
  echo "ERROR: Network verification failed" >&2
  exit 1
}

echo "EXP-002 | Network verification PASSED"
