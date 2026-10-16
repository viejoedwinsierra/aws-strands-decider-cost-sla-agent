#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_TAG="${PROJECT_TAG:-AWS-Cost-SLA-Decision-Agent}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

echo "EXP-001 | S3 bucket provisioning"

ACCOUNT_ID="$(aws_cli sts get-caller-identity \
  --query Account --output text)"

# Reuse a bucket saved in the current experiment configuration.
EXISTING_BUCKET=""
if [[ -f "$CONFIG_FILE" ]]; then
  EXISTING_BUCKET="$(grep '^EVIDENCE_BUCKET=' "$CONFIG_FILE" | tail -1 | cut -d= -f2- || true)"
fi

if [[ -n "$EXISTING_BUCKET" ]]; then
  echo "Checking configured bucket: $EXISTING_BUCKET"

  if ! aws_cli s3api head-bucket --bucket "$EXISTING_BUCKET"; then
    echo "ERROR: Configured evidence bucket is inaccessible." >&2
    echo "Bucket: $EXISTING_BUCKET" >&2
    echo "Refusing automatic replacement to protect evidence continuity." >&2
    exit 1
  fi

  BUCKET="$EXISTING_BUCKET"
  echo "Reusing bucket: $BUCKET"
else
  BUCKET="aws-cost-sla-evidence-${ACCOUNT_ID}-$(date +%s)"
  echo "Creating bucket: $BUCKET"

  aws_cli s3api create-bucket \\
    --bucket "$BUCKET" \\
    --region "$AWS_REGION"
fi

# Block all public access.
aws_cli s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
  'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'

# Enable default server-side encryption.
aws_cli s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Save bucket name without overwriting other configuration.
mkdir -p "$(dirname "$CONFIG_FILE")"

CONFIG_FILE="$CONFIG_FILE" BUCKET="$BUCKET" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["CONFIG_FILE"])
bucket = os.environ["BUCKET"]

lines = path.read_text().splitlines() if path.exists() else []
lines = [line for line in lines if not line.startswith("EVIDENCE_BUCKET=")]
lines.append(f"EVIDENCE_BUCKET={bucket}")

path.write_text("\n".join(lines) + "\n")
PY

echo "Bucket ready: $BUCKET"
echo "Configuration updated: $CONFIG_FILE"
