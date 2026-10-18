#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config/experiment.env"

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

: "${HTTP_INSTANCE_ID:?}"
: "${LOCUST_INSTANCE_ID:?}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

HTTP_JSON="$(aws_cli ec2 describe-instances --instance-ids "$HTTP_INSTANCE_ID" --output json)"
LOCUST_JSON="$(aws_cli ec2 describe-instances --instance-ids "$LOCUST_INSTANCE_ID" --output json)"

HTTP_JSON="$HTTP_JSON" LOCUST_JSON="$LOCUST_JSON" \
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" python3 "$SCRIPT_DIR/python/verify_security.py"
