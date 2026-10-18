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

echo "EXP-002 | Configure private EC2 networking"

WORKLOAD_SG="$(aws_cli ec2 describe-instances \
  --instance-ids "$WORKLOAD_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text)"

LOCUST_SG="$(aws_cli ec2 describe-instances \
  --instance-ids "$LOCUST_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text)"

[[ "$WORKLOAD_SG" == sg-* && "$LOCUST_SG" == sg-* ]] || {
  echo "ERROR: Invalid Security Group IDs" >&2
  exit 1
}

echo "Workload Security Group: $WORKLOAD_SG"
echo "Locust Security Group: $LOCUST_SG"

EXISTS="$(aws_cli ec2 describe-security-groups \
  --group-ids "$WORKLOAD_SG" \
  --query "SecurityGroups[0].IpPermissions[?IpProtocol=='tcp' && FromPort==\`8001\` && ToPort==\`8001\`].UserIdGroupPairs[].GroupId" \
  --output text)"

if [[ " $EXISTS " == *" $LOCUST_SG "* ]]; then
  echo "Private TCP 8001 rule already exists"
else
  aws_cli ec2 authorize-security-group-ingress \
    --group-id "$WORKLOAD_SG" \
    --protocol tcp \
    --port 8001 \
    --source-group "$LOCUST_SG"

  echo "Private TCP 8001 rule created"
fi

echo "EXP-002 | Network configuration PASSED"
