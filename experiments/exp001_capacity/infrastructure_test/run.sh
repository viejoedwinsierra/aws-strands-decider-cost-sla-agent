#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SCRIPT_DIR="$BASE_DIR/infrastructure"

CONFIG="$BASE_DIR/config/experiment.env"
[[ -f "$CONFIG" ]] || {
  echo "ERROR: Missing experiment.env" >&2
  exit 1
}

# Preserve explicit parameters provided by the sequence runner.
RUNNER_USERS="${USERS-}"
RUNNER_SPAWN_RATE="${SPAWN_RATE-}"
RUNNER_DURATION="${DURATION-}"
RUNNER_RUN_ID="${RUN_ID-}"

set -a
source "$CONFIG"
set +a

[[ -z "$RUNNER_USERS" ]] || USERS="$RUNNER_USERS"
[[ -z "$RUNNER_SPAWN_RATE" ]] || SPAWN_RATE="$RUNNER_SPAWN_RATE"
[[ -z "$RUNNER_DURATION" ]] || DURATION="$RUNNER_DURATION"
[[ -z "$RUNNER_RUN_ID" ]] || RUN_ID="$RUNNER_RUN_ID"

export AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

: "${EVIDENCE_BUCKET:?}"

export USERS="${USERS:-5}"
export SPAWN_RATE="${SPAWN_RATE:-1}"
export DURATION="${DURATION:-60s}"
export DURATION_SECONDS="${DURATION%s}"

export RUN_ID="${RUN_ID:-private_ec2_$(date -u +%Y%m%dT%H%M%SZ)}"

# Discover all running EC2 instances belonging to this experiment.
: "${PROJECT_TAG:?PROJECT_TAG is required}"
: "${EXPERIMENT_ID:?EXPERIMENT_ID is required}"
: "${ENVIRONMENT:?ENVIRONMENT is required}"

[[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || {
  echo "ERROR: Invalid RUN_ID" >&2
  exit 1
}

INVENTORY_FILE="$BASE_DIR/results/$RUN_ID/ec2_inventory.json"

python3 "$BASE_DIR/../shared/python/discover_instances.py" \
  --project "$PROJECT_TAG" \
  --experiment "$EXPERIMENT_ID" \
  --environment "$ENVIRONMENT" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" \
  --output "$INVENTORY_FILE"

# Resolve mandatory roles without discarding other discovered instances.
ROLE_IDS="$(python3 "$BASE_DIR/infrastructure_test/python/resolve_instance_roles.py" "$INVENTORY_FILE"
)"

mapfile -t INSTANCE_IDS <<< "$ROLE_IDS"
export HTTP_INSTANCE_ID="${INSTANCE_IDS[0]}"
export LOCUST_INSTANCE_ID="${INSTANCE_IDS[1]}"

echo "EXP-001 | EC2 inventory: $INVENTORY_FILE"
echo "HTTP instance: $HTTP_INSTANCE_ID"
echo "Locust instance: $LOCUST_INSTANCE_ID"

# Persist the frozen EC2 inventory before running the experiment.
S3_RUN_PREFIX="s3://${EVIDENCE_BUCKET}/experiments/exp001_capacity/results/${RUN_ID}"

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" s3 cp \
  "$INVENTORY_FILE" \
  "$S3_RUN_PREFIX/ec2_inventory.json" \
  --sse AES256 --no-progress

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" s3api head-object \
  --bucket "$EVIDENCE_BUCKET" \
  --key "experiments/exp001_capacity/results/${RUN_ID}/ec2_inventory.json" \
  --query '{Size:ContentLength,Encryption:ServerSideEncryption}' \
  --output json

# Verify that the S3 object matches the local inventory byte for byte.
python3 "$BASE_DIR/infrastructure_test/python/verify_s3_integrity.py" "$INVENTORY_FILE" "$S3_RUN_PREFIX/ec2_inventory.json" "$AWS_PROFILE" "$AWS_REGION"

echo "EXP-001 | EC2 inventory published and verified in S3"


# Stop after EC2 discovery when running an infrastructure validation.
if [[ "${DISCOVERY_ONLY:-0}" == "1" ]]; then
  echo "EXP-001 | Discovery-only validation completed"
  exit 0
fi

echo "=================================="
echo "EXP-001 | Automated Experiment"
echo "Run ID: $RUN_ID"
echo "=================================="

echo "[1/5] Verify HTTP and security"
bash "$SCRIPT_DIR/verify_security.sh"
bash "$SCRIPT_DIR/verify.sh"

echo "[2/5] Verify Locust and network"
bash "$SCRIPT_DIR/verify_locust.sh"
bash "$SCRIPT_DIR/verify_network.sh"

# PRE: establish the baseline observation window before load generation.
PRE_DURATION_SECONDS=60
START_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PRE_START_TIME="$START_TIME"

echo "EXP-001 | PRE started: $PRE_START_TIME"
sleep "$PRE_DURATION_SECONDS"
PRE_END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "EXP-001 | PRE completed: $PRE_END_TIME"

export REQUIRE_RUN_MANIFEST=1

echo "[3/5] Execute load test"

# RUN: measure the operational execution window, including SSM and evidence transfer.
RUN_START_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "EXP-001 | RUN started: $RUN_START_TIME"

LOAD_STATUS=0
bash "$BASE_DIR/infrastructure_test/run_load.sh" || LOAD_STATUS=$?

RUN_END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "EXP-001 | RUN completed: $RUN_END_TIME | status=$LOAD_STATUS"

# POST: observe the infrastructure after the load execution.
POST_DURATION_SECONDS=60
POST_START_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "EXP-001 | POST started: $POST_START_TIME"

sleep "$POST_DURATION_SECONDS"

POST_END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
END_TIME="$POST_END_TIME"

echo "EXP-001 | POST completed: $POST_END_TIME"
echo "EXP-001 | CloudWatch observation window: $START_TIME -> $END_TIME"

# Persist the complete experiment timeline before CloudWatch collection.
TIMELINE_FILE="$BASE_DIR/results/$RUN_ID/experiment_timeline.json"
mkdir -p "$(dirname "$TIMELINE_FILE")"

python3 "$BASE_DIR/infrastructure_test/python/generate_timeline.py" "$TIMELINE_FILE" \
  "$EXPERIMENT_ID" "$RUN_ID" "$LOAD_STATUS" \
  "$PRE_START_TIME" "$PRE_END_TIME" \
  "$RUN_START_TIME" "$RUN_END_TIME" \
  "$POST_START_TIME" "$POST_END_TIME"

# CloudWatch collection runs only after PRE, RUN and POST have completed.
# Use every EC2 instance from the frozen experiment inventory.
CLOUDWATCH_INSTANCE_OUTPUT="$(
  python3 "$BASE_DIR/infrastructure_test/python/list_cloudwatch_instances.py" "$INVENTORY_FILE"
)" || {
  echo "ERROR: CloudWatch instance discovery failed" >&2
  exit 1
}

mapfile -t CLOUDWATCH_INSTANCE_IDS <<< "$CLOUDWATCH_INSTANCE_OUTPUT"

echo "EXP-001 | CloudWatch targets: ${CLOUDWATCH_INSTANCE_IDS[*]}"

# Query historical CloudWatch metrics only after PRE, RUN and POST.
CLOUDWATCH_STATUS=0
CLOUDWATCH_OUTPUT_DIR="$BASE_DIR/results/$RUN_ID/cloudwatch"

echo "EXP-001 | Exporting CloudWatch metrics"
echo "EXP-001 | Observation window: $START_TIME -> $END_TIME"

python3 "$BASE_DIR/../shared/cloudwatch/export_metrics.py" \
  --instance-ids "${CLOUDWATCH_INSTANCE_IDS[@]}" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" \
  --experiment "$EXPERIMENT_ID" \
  --run-id "$RUN_ID" \
  --output-dir "$CLOUDWATCH_OUTPUT_DIR" \
  --period 300 || CLOUDWATCH_STATUS=$?

echo "EXP-001 | CloudWatch export status: $CLOUDWATCH_STATUS"

# Publish timeline and CloudWatch evidence under the current RUN_ID.
EVIDENCE_PREFIX="s3://$EVIDENCE_BUCKET/experiments/exp001_capacity/results/$RUN_ID"
EVIDENCE_UPLOAD_STATUS=0

aws s3 cp "$TIMELINE_FILE" "$EVIDENCE_PREFIX/experiment_timeline.json" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" || EVIDENCE_UPLOAD_STATUS=$?

if (( CLOUDWATCH_STATUS == 0 )); then
  for instance_id in "${CLOUDWATCH_INSTANCE_IDS[@]}"; do
    metric_file="$CLOUDWATCH_OUTPUT_DIR/$instance_id.json"

    if [[ ! -s "$metric_file" ]]; then
      echo "ERROR: Missing CloudWatch evidence: $metric_file" >&2
      CLOUDWATCH_STATUS=1
      break
    fi
  done
fi

if (( CLOUDWATCH_STATUS == 0 )); then
  for instance_id in "${CLOUDWATCH_INSTANCE_IDS[@]}"; do
    metric_file="$CLOUDWATCH_OUTPUT_DIR/$instance_id.json"

    aws s3 cp "$metric_file" "$EVIDENCE_PREFIX/cloudwatch/$instance_id.json" \
      --profile "$AWS_PROFILE" \
      --region "$AWS_REGION" || EVIDENCE_UPLOAD_STATUS=$?
  done
else
  echo "WARNING: CloudWatch evidence upload skipped; export incomplete" >&2
fi

echo "EXP-001 | Evidence upload status: $EVIDENCE_UPLOAD_STATUS"

echo "[4/5] Normalize and evaluate SLA"
ANALYSIS_STATUS=0
STATS_FILE="$BASE_DIR/results/$RUN_ID/exp001_stats.csv"

if [[ -s "$STATS_FILE" ]]; then
  bash "$BASE_DIR/infrastructure_test/analyze_results.sh" "$RUN_ID" || ANALYSIS_STATUS=$?
else
  echo "WARNING: No statistics available; SLA cannot be evaluated" >&2
  ANALYSIS_STATUS=1
fi

echo "[5/5] Archive and verify evidence"
ARCHIVE_STATUS=0
REQUIRE_EC2_INVENTORY=1 \
REQUIRE_CLOUDWATCH_EVIDENCE=1 \
  bash "$BASE_DIR/infrastructure_test/archive_evidence.sh" "$RUN_ID" || ARCHIVE_STATUS=$?

if (( LOAD_STATUS != 0 || CLOUDWATCH_STATUS != 0 || EVIDENCE_UPLOAD_STATUS != 0 || ANALYSIS_STATUS != 0 || ARCHIVE_STATUS != 0 )); then
  echo "EXP-001 | INCOMPLETE OR FAILED" >&2
  echo "Load=$LOAD_STATUS CloudWatch=$CLOUDWATCH_STATUS Upload=$EVIDENCE_UPLOAD_STATUS Analysis=$ANALYSIS_STATUS Archive=$ARCHIVE_STATUS" >&2
  exit 1
fi

echo "=================================="
echo "EXP-001 | COMPLETED"
echo "Run ID: $RUN_ID"
echo "S3 and local evidence archived"
echo "=================================="
