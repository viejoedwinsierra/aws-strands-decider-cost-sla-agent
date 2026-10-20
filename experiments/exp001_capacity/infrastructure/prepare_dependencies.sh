#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

[[ -f "$CONFIG_FILE" ]] || {
  echo "ERROR: experiment.env not found" >&2
  exit 1
}

# bootstrap_all.sh supplies the shared AWS/project environment.
: "${AWS_PROFILE:?AWS_PROFILE must be provided by bootstrap_all.sh}"
: "${AWS_REGION:?AWS_REGION must be provided by bootstrap_all.sh}"
: "${EXPERIMENT_ID:?EXPERIMENT_ID must be provided by bootstrap_all.sh}"

set -a
source "$CONFIG_FILE"
set +a
: "${EVIDENCE_BUCKET:?Missing EVIDENCE_BUCKET}"

WHEEL_DIR="${TMPDIR:-/tmp}/exp001-locust-python311-wheels"
S3_PREFIX="s3://${EVIDENCE_BUCKET}/dependencies/locust/python311-linux-x86_64/"
LOG_DIR="${TMPDIR:-/tmp}/exp001-dependency-logs"
LOG_FILE="${LOG_DIR}/prepare_dependencies_$(date -u +%Y%m%dT%H%M%SZ)_$$.log"

mkdir -p "$WHEEL_DIR" "$LOG_DIR"

run_logged() {
  local description="$1"
  shift
  echo "$EXPERIMENT_ID | $description..."
  printf '\n=== %s | %s ===\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$description" >> "$LOG_FILE"
  if "$@" >> "$LOG_FILE" 2>&1; then
    return 0
  else
    local status=$?
    echo "$EXPERIMENT_ID | FAILED: $description (exit $status)" >&2
    echo "$EXPERIMENT_ID | Detailed log: $LOG_FILE" >&2
    echo "$EXPERIMENT_ID | Last 20 log lines:" >&2
    tail -n 20 "$LOG_FILE" >&2
    exit "$status"
  fi
}

echo "$EXPERIMENT_ID | Preparing Locust dependencies"

run_logged "Downloading Python wheels" \
  python3 -m pip download \
    --dest "$WHEEL_DIR" \
    --only-binary=:all: \
    --python-version 3.11 \
    --implementation cp \
    --abi cp311 \
    --platform manylinux2014_x86_64 \
    'locust==2.46.7' \
    'typing-extensions>=4.6.0'

run_logged "Uploading wheels to S3" \
  aws s3 sync \
    "$WHEEL_DIR/" \
    "$S3_PREFIX" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --exclude "*" \
    --include "*.whl" \
    --sse AES256

echo "$EXPERIMENT_ID | Dependency preparation completed"
echo "$EXPERIMENT_ID | S3: $S3_PREFIX"
echo "$EXPERIMENT_ID | Detailed log: $LOG_FILE"
