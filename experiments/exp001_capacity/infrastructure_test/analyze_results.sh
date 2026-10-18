#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$BASE_DIR/config/experiment.env"

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

RUN_ID="${1:?Usage: analyze_results.sh RUN_ID}"
[[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || {
  echo "ERROR: Invalid RUN_ID" >&2
  exit 1
}

: "${EVIDENCE_BUCKET:?EVIDENCE_BUCKET is required}"

RESULTS_DIR="$BASE_DIR/results/$RUN_ID"
S3_PREFIX="s3://$EVIDENCE_BUCKET/experiments/exp001_capacity/results/$RUN_ID"

[[ -s "$RESULTS_DIR/exp001_stats.csv" ]] || {
  echo "ERROR: Missing exp001_stats.csv" >&2
  exit 1
}

HTTP_PRIVATE_IP="$(
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    ec2 describe-instances \
    --instance-ids "$HTTP_INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PrivateIpAddress' \
    --output text
)"

[[ "$HTTP_PRIVATE_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "ERROR: Invalid HTTP private IP" >&2
  exit 1
}

python3 "$BASE_DIR/metrics/normalize_locust.py" \
  --run-id "$RUN_ID" \
  --users "${USERS:-5}" \
  --spawn-rate "${SPAWN_RATE:-1}" \
  --duration "${DURATION_SECONDS:-60}" \
  --target-ip "$HTTP_PRIVATE_IP"

python3 "$BASE_DIR/metrics/evaluate_sla.py" \
  --run-id "$RUN_ID"

for filename in metrics_normalized.json sla_evaluation.json; do
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    s3 cp "$RESULTS_DIR/$filename" \
    "$S3_PREFIX/$filename" \
    --sse AES256 \
    --no-progress
done

echo "EXP-001 | Analysis completed"
echo "Local: $RESULTS_DIR"
echo "S3: $S3_PREFIX/"
