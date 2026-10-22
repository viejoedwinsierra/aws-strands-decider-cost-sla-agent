#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$BASE_DIR/config/experiment.env"

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
RUN_ID="${1:?Usage: archive_evidence.sh RUN_ID}"

[[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || {
  echo "ERROR: Invalid RUN_ID" >&2
  exit 1
}

: "${EVIDENCE_BUCKET:?}"

RESULTS_DIR="$BASE_DIR/results/$RUN_ID"
S3_PREFIX="s3://$EVIDENCE_BUCKET/experiments/exp001_capacity/results/$RUN_ID"

mkdir -p "$RESULTS_DIR"

# Download to Linux filesystem to avoid WSL2 /mnt/c timestamp errors.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  s3 cp "$S3_PREFIX/" "$TMP_DIR/" \
  --recursive --exclude "*" \
  --include "exp001_*.csv" \
  --include "metrics_normalized.json" \
  --include "sla_evaluation.json" \
  --include "run_manifest.json" \
  --include "ec2_inventory.json" \
  --include "experiment_timeline.json" \
  --include "cloudwatch/*.json" \
  --include "diagnostics/ssm_locust_execution.json" \
  --no-progress

# Copy only evidence actually retrieved from S3.
# Avoid retaining stale local files from previous archive attempts.
shopt -s nullglob
evidence_files=(
  "$TMP_DIR"/exp001_*.csv
  "$TMP_DIR"/metrics_normalized.json
  "$TMP_DIR"/sla_evaluation.json
  "$TMP_DIR"/run_manifest.json
  "$TMP_DIR"/ec2_inventory.json
  "$TMP_DIR"/experiment_timeline.json
  "$TMP_DIR"/cloudwatch/*.json
  "$TMP_DIR"/diagnostics/ssm_locust_execution.json
)

if (( ${#evidence_files[@]} == 0 )); then
  echo "ERROR: No evidence found in S3 for $RUN_ID" >&2
  exit 1
fi

if [[ "${REQUIRE_RUN_MANIFEST:-0}" == "1" &&
      ! -f "$TMP_DIR/run_manifest.json" ]]; then
  echo "ERROR: Required run_manifest.json missing from S3" >&2
  exit 1
fi

# Require the EC2 inventory for new experiment executions.
# Historical runs remain compatible when this flag is not enabled.
if [[ "${REQUIRE_EC2_INVENTORY:-0}" == "1" &&
      ! -f "$TMP_DIR/ec2_inventory.json" ]]; then
  echo "ERROR: Required ec2_inventory.json missing from S3" >&2
  exit 1
fi

# Remove stale local evidence before restoring the S3 snapshot.
for name in \
  exp001_stats.csv \
  exp001_stats_history.csv \
  exp001_failures.csv \
  exp001_exceptions.csv \
  metrics_normalized.json \
  sla_evaluation.json \
  run_manifest.json \
  ec2_inventory.json \
  experiment_timeline.json \
  evidence_manifest.json; do
  rm -f "$RESULTS_DIR/$name"
done

# Remove stale CloudWatch evidence before restoring S3 snapshot.
rm -rf -- "$RESULTS_DIR/cloudwatch"
rm -f -- "$RESULTS_DIR/diagnostics/ssm_locust_execution.json"

RECOVERED_COUNT=0
for file in "${evidence_files[@]}"; do
  [[ -f "$file" ]] || continue
  relative_path="${file#"$TMP_DIR"/}"
  destination="$RESULTS_DIR/$relative_path"
  mkdir -p "$(dirname "$destination")"
  cp "$file" "$destination"
  RECOVERED_COUNT=$((RECOVERED_COUNT + 1))
done

echo "Evidence files recovered: $RECOVERED_COUNT"

python3 "$SCRIPT_DIR/python/archive_evidence.py" generate "$RESULTS_DIR" "$RUN_ID" "${REQUIRE_CLOUDWATCH_EVIDENCE:-0}"

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  s3 cp "$RESULTS_DIR/evidence_manifest.json" \
  "$S3_PREFIX/evidence_manifest.json" \
  --sse AES256 --no-progress

# Confirm that S3 contains exactly the manifest just generated.
TMP_MANIFEST="$(mktemp)"
trap 'rm -rf "$TMP_DIR"; rm -f "$TMP_MANIFEST"' EXIT

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  s3 cp "$S3_PREFIX/evidence_manifest.json" \
  "$TMP_MANIFEST" --no-progress

python3 "$SCRIPT_DIR/python/archive_evidence.py" verify-local "$RESULTS_DIR" "$TMP_MANIFEST"

# Independently verify each archived object against S3.
python3 "$SCRIPT_DIR/python/archive_evidence.py" verify-remote "$RESULTS_DIR/evidence_manifest.json" "$S3_PREFIX" "$AWS_PROFILE" "$AWS_REGION"

# Integrity alone does not guarantee evidence completeness.
python3 "$SCRIPT_DIR/python/archive_evidence.py" check-completeness "$RESULTS_DIR/evidence_manifest.json"

echo "S3 archive: $S3_PREFIX/"
echo "Local backup: $RESULTS_DIR"
