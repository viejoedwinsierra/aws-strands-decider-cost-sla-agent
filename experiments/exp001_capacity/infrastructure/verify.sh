#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
if [[ -f "$CONFIG_FILE" ]]; then
  set -a; source "$CONFIG_FILE"; set +a
fi
: "${AWS_PROFILE:?}" "${AWS_REGION:?}" "${INSTANCE_ID:?}"
aws_cli() { aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }
echo "EXP-001 | Verify | $INSTANCE_ID"
STATE="$(aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text)"
[[ "$STATE" == running ]] || { echo "EC2 not running: $STATE" >&2; exit 1; }
PING="$(aws_cli ssm describe-instance-information --filters "Key=InstanceIds,Values=$INSTANCE_ID" --query 'InstanceInformationList[0].PingStatus' --output text)"
[[ "$PING" == Online ]] || { echo "SSM not Online: $PING" >&2; exit 1; }
COMMAND_ID="$(aws_cli ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript --parameters 'commands=["systemctl is-active --quiet exp001-http && curl -fsS http://127.0.0.1:8080/health"]' --query Command.CommandId --output text)"
aws_cli ssm wait command-executed --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"
aws_cli ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --query '{Status:Status,Output:StandardOutputContent,Errors:StandardErrorContent}' --output json
