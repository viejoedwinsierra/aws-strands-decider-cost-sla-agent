#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
TAGS_HELPER="${SCRIPT_DIR}/../../shared/python/resource_tags.py"

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

# Reuse only a bucket whose owner and experiment identity are verified.
EXISTING_BUCKET=""
if [[ -f "$CONFIG_FILE" ]]; then
  EXISTING_BUCKET="$(grep '^EVIDENCE_BUCKET=' "$CONFIG_FILE" | tail -1 | cut -d= -f2- || true)"
fi

if [[ ! -f "$TAGS_HELPER" ]]; then
  echo "$EXPERIMENT_ID | ERROR: Missing Python helper: $TAGS_HELPER" >&2
  exit 1
fi

CREATE_BUCKET=false

if [[ -n "$EXISTING_BUCKET" ]]; then
  echo "Checking configured bucket: $EXISTING_BUCKET"

  HEAD_STATUS="$(aws_cli s3api head-bucket \
    --bucket "$EXISTING_BUCKET" \
    --expected-bucket-owner "$ACCOUNT_ID" \
    --query 'ResponseMetadata.HTTPStatusCode' \
    --output text 2>&1)" && HEAD_EXIT=0 || HEAD_EXIT=$?

  if [[ "$HEAD_EXIT" -eq 0 ]]; then
    BUCKET="$EXISTING_BUCKET"
    echo "$EXPERIMENT_ID | Validating bucket identity"

    aws_cli s3api get-bucket-tagging \
      --bucket "$BUCKET" \
      --expected-bucket-owner "$ACCOUNT_ID" \
      --output json |
      python3 "$TAGS_HELPER" s3 check-identity \
        --name "$BUCKET" --role "evidence-storage"

    echo "Reusing verified bucket: $BUCKET"
  elif [[ "$HEAD_STATUS" == *"(404)"* ]]; then
    echo "$EXPERIMENT_ID | Configured bucket no longer exists."
    echo "$EXPERIMENT_ID | Provisioning replacement bucket."
    CREATE_BUCKET=true
  else
    echo "$EXPERIMENT_ID | ERROR: Cannot verify configured bucket." >&2
    echo "$HEAD_STATUS" >&2
    exit 1
  fi
else
  CREATE_BUCKET=true
fi

if [[ "$CREATE_BUCKET" == true ]]; then
  BUCKET="aws-cost-sla-evidence-${ACCOUNT_ID}-$(date +%s)"
  echo "Creating bucket: $BUCKET"

  aws_cli s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$AWS_REGION"
fi

# Block all public access.
aws_cli s3api put-public-access-block \
  --bucket "$BUCKET" \
  --expected-bucket-owner "$ACCOUNT_ID" \
  --public-access-block-configuration \
  'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'

# Enable default server-side encryption.
aws_cli s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --expected-bucket-owner "$ACCOUNT_ID" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Read existing tags, preserving any unrelated tags on a reused bucket.
# AWS returns NoSuchTagSet for a bucket with no tags.

CURRENT_TAGS_FILE="$(mktemp)"
MERGED_TAGS_FILE="$(mktemp)"
TAG_ERROR_FILE="$(mktemp)"
trap 'rm -f "$CURRENT_TAGS_FILE" "$MERGED_TAGS_FILE" "$TAG_ERROR_FILE"' EXIT

echo "$EXPERIMENT_ID | Reading existing S3 bucket tags"
if aws_cli s3api get-bucket-tagging --bucket "$BUCKET" \
    --expected-bucket-owner "$ACCOUNT_ID" \
    --output json > "$CURRENT_TAGS_FILE" 2> "$TAG_ERROR_FILE"; then
  python3 "$TAGS_HELPER" s3 merge --name "$BUCKET" --role "evidence-storage" < "$CURRENT_TAGS_FILE" > "$MERGED_TAGS_FILE"
elif grep -q 'NoSuchTagSet' "$TAG_ERROR_FILE"; then
  python3 "$TAGS_HELPER" s3 build --name "$BUCKET" --role "evidence-storage" > "$MERGED_TAGS_FILE"
else
  echo "$EXPERIMENT_ID | ERROR: Unable to read S3 bucket tags" >&2
  cat "$TAG_ERROR_FILE" >&2
  exit 1
fi

echo "$EXPERIMENT_ID | Applying S3 bucket tags"
aws_cli s3api put-bucket-tagging \
  --bucket "$BUCKET" \
  --expected-bucket-owner "$ACCOUNT_ID" \
  --tagging "file://$MERGED_TAGS_FILE"

# Fail provisioning if AWS does not return all required tags.
echo "$EXPERIMENT_ID | Verifying S3 bucket tags"
aws_cli s3api get-bucket-tagging --bucket "$BUCKET" --expected-bucket-owner "$ACCOUNT_ID" --output json \
  | python3 "$TAGS_HELPER" s3 validate --name "$BUCKET" --role "evidence-storage"

# Save bucket name without overwriting other configuration.
mkdir -p "$(dirname "$CONFIG_FILE")"
CONFIG_FILE="$CONFIG_FILE" BUCKET="$BUCKET" \
  python3 "$SCRIPT_DIR/python/save_bucket_config.py"

echo "Bucket ready: $BUCKET"
echo "Configuration updated: $CONFIG_FILE"
