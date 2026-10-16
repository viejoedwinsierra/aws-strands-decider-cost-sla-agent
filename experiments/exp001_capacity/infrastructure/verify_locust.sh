#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

[[ -f "$CONFIG_FILE" ]] || {
  echo "ERROR: Missing $CONFIG_FILE" >&2
  exit 1
}

set -a
source "$CONFIG_FILE"
set +a

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

: "${LOCUST_INSTANCE_ID:?Missing LOCUST_INSTANCE_ID}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

echo "EXP-001 | Verify Locust | $LOCUST_INSTANCE_ID"

COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$LOCUST_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "EXP-001 Locust verification" \
  --parameters 'commands=["set -eu","/opt/exp001-locust/venv311/bin/locust --version | grep -F \"locust 2.46.7\"","/opt/exp001-locust/venv311/bin/python -m pip check","test -f /opt/exp001-locust/locustfile.py","echo LOCUST_VERIFICATION_PASSED"]' \
  --query 'Command.CommandId' \
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

if [[ "$STATUS" != "Success" ]]; then
  echo "ERROR: Locust verification failed." >&2
  exit 1
fi

echo "EXP-001 | Locust verification PASSED"
