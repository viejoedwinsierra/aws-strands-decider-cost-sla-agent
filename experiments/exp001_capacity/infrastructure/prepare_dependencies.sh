#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

[[ -f "$CONFIG_FILE" ]] || {
  echo "ERROR: experiment.env not found" >&2
  exit 1
}

set -a
source "$CONFIG_FILE"
set +a

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

: "${EVIDENCE_BUCKET:?Missing EVIDENCE_BUCKET}"

WHEEL_DIR="${TMPDIR:-/tmp}/exp001-locust-python311-wheels"
S3_PREFIX="s3://${EVIDENCE_BUCKET}/dependencies/locust/python311-linux-x86_64/"

mkdir -p "$WHEEL_DIR"

echo "EXP-001 | Preparing Locust dependencies"

python3 -m pip download \
  --dest "$WHEEL_DIR" \
  --only-binary=:all: \
  --python-version 3.11 \
  --implementation cp \
  --abi cp311 \
  --platform manylinux2014_x86_64 \
  'locust==2.46.7' \
  'typing-extensions>=4.6.0'

echo "Uploading wheels to S3..."

aws s3 sync \
  "$WHEEL_DIR/" \
  "$S3_PREFIX" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --exclude "*" \
  --include "*.whl" \
  --sse AES256

echo "Dependency preparation completed."
echo "S3: $S3_PREFIX"
