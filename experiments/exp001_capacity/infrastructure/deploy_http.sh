#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
SERVER_FILE="${SCRIPT_DIR}/../application/server.py"

[[ -f "$CONFIG_FILE" ]] || { echo "Missing config: $CONFIG_FILE" >&2; exit 1; }
[[ -f "$SERVER_FILE" ]] || { echo "Missing server: $SERVER_FILE" >&2; exit 1; }

set -a
source "$CONFIG_FILE"
set +a

: "${AWS_PROFILE:?}"
: "${AWS_REGION:?}"
: "${INSTANCE_ID:?}"

echo "EXP-001 | Deploy HTTP server to $INSTANCE_ID"

STATE=$(aws ec2 describe-instances \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text)

[[ "$STATE" == "running" ]] || {
  echo "ERROR: EC2 is not running: $STATE" >&2
  exit 1
}

# Encode the exact local source to transfer it safely through SSM.
SERVER_B64=$(base64 -w 0 "$SERVER_FILE")

COMMAND_ID=$(aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "EXP-001 HTTP server deployment" \
  --parameters "commands=[
    \"set -eu\",
    \"mkdir -p /opt/exp001-http\",
    \"echo '$SERVER_B64' | base64 -d > /opt/exp001-http/server.py\",
    \"printf '[Unit]\\nDescription=EXP-001 HTTP Server\\nAfter=network.target\\n[Service]\\nType=simple\\nUser=root\\nWorkingDirectory=/opt/exp001-http\\nEnvironment=HTTP_HOST=0.0.0.0\\nEnvironment=HTTP_PORT=8080\\nExecStart=/usr/bin/python3 /opt/exp001-http/server.py\\nRestart=on-failure\\n[Install]\\nWantedBy=multi-user.target\\n' > /etc/systemd/system/exp001-http.service\",
    \"systemctl daemon-reload\",
    \"systemctl enable --now exp001-http\",
    \"systemctl restart exp001-http\",
    \"curl --fail --silent --show-error --retry 5 --retry-delay 1 http://127.0.0.1:8080/health\"
  ]" \
  --query 'Command.CommandId' \
  --output text)

echo "SSM Command ID: $COMMAND_ID"
echo "Waiting for deployment..."

if ! aws ssm wait command-executed \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID"; then
  echo "SSM deployment did not complete successfully." >&2
fi

aws ssm get-command-invocation \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Output:StandardOutputContent,Errors:StandardErrorContent}' \
  --output json

STATUS=$(aws ssm get-command-invocation \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query Status \
  --output text)

[[ "$STATUS" == "Success" ]] || exit 1
