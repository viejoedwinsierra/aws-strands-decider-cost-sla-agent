#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
SERVER_FILE="${SCRIPT_DIR}/../application/server.py"
if [[ -f "$CONFIG_FILE" ]]; then
  # The orchestrator exports current values; local file is for standalone runs.
  set -a
  source "$CONFIG_FILE"
  set +a
fi
: "${AWS_PROFILE:?}" "${AWS_REGION:?}" "${INSTANCE_ID:?}"
[[ -f "$SERVER_FILE" ]] || { echo "Missing server: $SERVER_FILE" >&2; exit 1; }
aws_cli() { aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }

# JSON parameter file avoids fragile nested shell quoting.
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
SERVER_FILE="$SERVER_FILE" python3 "$SCRIPT_DIR/python/build_http_ssm.py" "$TMP"

echo "EXP-001 | HTTP deploy | $INSTANCE_ID"
COMMAND_ID="$(aws_cli ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript --comment 'EXP-001 idempotent HTTP deployment' --parameters "file://$TMP" --query Command.CommandId --output text)"
if ! aws_cli ssm wait command-executed --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"; then
  echo 'SSM command ended without Success; inspecting result...' >&2
fi
aws_cli ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --query '{Status:Status,Output:StandardOutputContent,Errors:StandardErrorContent}' --output json
STATUS="$(aws_cli ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --query Status --output text)"
[[ "$STATUS" == 'Success' ]] || exit 1
