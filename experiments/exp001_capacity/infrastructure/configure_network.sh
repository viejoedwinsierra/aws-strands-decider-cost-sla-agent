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

: "${HTTP_INSTANCE_ID:?}"
: "${LOCUST_INSTANCE_ID:?}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

echo "EXP-001 | Configure private EC2 networking"

HTTP_SG="$(aws_cli ec2 describe-instances \
  --instance-ids "$HTTP_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text)"

LOCUST_SG="$(aws_cli ec2 describe-instances \
  --instance-ids "$LOCUST_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text)"

[[ "$HTTP_SG" == sg-* && "$LOCUST_SG" == sg-* ]] || {
  echo "ERROR: Invalid Security Group IDs" >&2
  exit 1
}

echo "HTTP Security Group: $HTTP_SG"
echo "Locust Security Group: $LOCUST_SG"

EXISTS="$(aws_cli ec2 describe-security-groups \
  --group-ids "$HTTP_SG" \
  --query "SecurityGroups[0].IpPermissions[?IpProtocol=='tcp' && FromPort==\`8080\` && ToPort==\`8080\`].UserIdGroupPairs[].GroupId" \
  --output text)"

if [[ " $EXISTS " == *" $LOCUST_SG "* ]]; then
  echo "Private TCP 8080 rule already exists"
else
  aws_cli ec2 authorize-security-group-ingress \
    --group-id "$HTTP_SG" \
    --protocol tcp \
    --port 8080 \
    --source-group "$LOCUST_SG"

  echo "Private TCP 8080 rule created"
fi

echo "EXP-001 | Network configuration PASSED"
