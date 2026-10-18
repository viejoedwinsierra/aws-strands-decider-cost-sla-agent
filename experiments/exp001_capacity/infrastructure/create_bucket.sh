#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
HISTORY_FILE="${SCRIPT_DIR}/../config/evidence_bucket_history.json"
TAGS_HELPER="${SCRIPT_DIR}/python/bucket_tags.py"

# Configuration is exported by load_environment.sh via bootstrap_all.sh.
: "${AWS_PROFILE:?AWS_PROFILE must be exported by bootstrap_all.sh}"
: "${AWS_REGION:?AWS_REGION must be exported by bootstrap_all.sh}"
: "${PROJECT_TAG:?PROJECT_TAG must be exported by bootstrap_all.sh}"
: "${EXPERIMENT_ID:?EXPERIMENT_ID must be exported by bootstrap_all.sh}"
: "${ENVIRONMENT:?ENVIRONMENT must be exported by bootstrap_all.sh}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

echo "$EXPERIMENT_ID | S3 bucket provisioning"

ACCOUNT_ID="$(aws_cli sts get-caller-identity --query Account --output text)"

# Reuse a bucket saved in the current experiment configuration.
EXISTING_BUCKET=""
if [[ -f "$CONFIG_FILE" ]]; then
  EXISTING_BUCKET="$(grep '^EVIDENCE_BUCKET=' "$CONFIG_FILE" | tail -1 | cut -d= -f2- || true)"
fi

if [[ -n "$EXISTING_BUCKET" ]]; then
  echo "Checking configured bucket: $EXISTING_BUCKET"

  if aws_cli s3api head-bucket --bucket "$EXISTING_BUCKET" >/dev/null 2>&1; then
    BUCKET="$EXISTING_BUCKET"
    echo "Reusing bucket: $BUCKET"
  else
    echo "Previous bucket unavailable: $EXISTING_BUCKET"
    echo "Preserving historical reference and creating a new bucket."

    HISTORY_FILE="$HISTORY_FILE" OLD_BUCKET="$EXISTING_BUCKET" \
      python3 "$SCRIPT_DIR/python/bucket_history.py"

    BUCKET="aws-cost-sla-evidence-${ACCOUNT_ID}-$(date +%s)"
    echo "Creating bucket: $BUCKET"
    aws_cli s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION"
  fi
else
  BUCKET="aws-cost-sla-evidence-${ACCOUNT_ID}-$(date +%s)"
  echo "Creating bucket: $BUCKET"

  aws_cli s3api create-bucket \
    --bucket "$BUCKET" \
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

# Read existing tags, preserving any unrelated tags on a reused bucket.
# AWS returns NoSuchTagSet for a bucket with no tags.
if [[ ! -f "$TAGS_HELPER" ]]; then
  echo "$EXPERIMENT_ID | ERROR: Missing Python helper: $TAGS_HELPER" >&2
  exit 1
fi

CURRENT_TAGS_FILE="$(mktemp)"
MERGED_TAGS_FILE="$(mktemp)"
TAG_ERROR_FILE="$(mktemp)"
trap 'rm -f "$CURRENT_TAGS_FILE" "$MERGED_TAGS_FILE" "$TAG_ERROR_FILE"' EXIT

echo "$EXPERIMENT_ID | Reading existing S3 bucket tags"
if aws_cli s3api get-bucket-tagging --bucket "$BUCKET" \
    --output json > "$CURRENT_TAGS_FILE" 2> "$TAG_ERROR_FILE"; then
  python3 "$TAGS_HELPER" merge < "$CURRENT_TAGS_FILE" > "$MERGED_TAGS_FILE"
elif grep -q 'NoSuchTagSet' "$TAG_ERROR_FILE"; then
  python3 "$TAGS_HELPER" build > "$MERGED_TAGS_FILE"
else
  echo "$EXPERIMENT_ID | ERROR: Unable to read S3 bucket tags" >&2
  cat "$TAG_ERROR_FILE" >&2
  exit 1
fi

echo "$EXPERIMENT_ID | Applying S3 bucket tags"
aws_cli s3api put-bucket-tagging \
  --bucket "$BUCKET" \
  --tagging "file://$MERGED_TAGS_FILE"

# Fail provisioning if AWS does not return all required tags.
echo "$EXPERIMENT_ID | Verifying S3 bucket tags"
aws_cli s3api get-bucket-tagging --bucket "$BUCKET" --output json \
  | python3 "$TAGS_HELPER" validate

# Save bucket name without overwriting other configuration.
mkdir -p "$(dirname "$CONFIG_FILE")"
CONFIG_FILE="$CONFIG_FILE" BUCKET="$BUCKET" \
  python3 "$SCRIPT_DIR/python/save_bucket_config.py"

echo "Bucket ready: $BUCKET"
echo "Configuration updated: $CONFIG_FILE"
