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

LOCUST_FILE="$LOCUST_FILE" EVIDENCE_BUCKET="$EVIDENCE_BUCKET" python3 "$SCRIPT_DIR/python/build_locust_ssm.py" "$TMP"

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
