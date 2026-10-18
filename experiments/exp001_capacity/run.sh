#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"
SCRIPT_DIR="$BASE_DIR/infrastructure"

CONFIG="$BASE_DIR/config/experiment.env"
[[ -f "$CONFIG" ]] || {
  echo "ERROR: Missing experiment.env" >&2
  exit 1
}

set -a
source "$CONFIG"
set +a

export AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

: "${HTTP_INSTANCE_ID:?}"
: "${LOCUST_INSTANCE_ID:?}"
: "${EVIDENCE_BUCKET:?}"

export USERS="${USERS:-5}"
export SPAWN_RATE="${SPAWN_RATE:-1}"
export DURATION="${DURATION:-60s}"
export DURATION_SECONDS="${DURATION%s}"

export RUN_ID="private_ec2_$(date -u +%Y%m%dT%H%M%SZ)"

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

export REQUIRE_RUN_MANIFEST=1

echo "[3/5] Execute load test"
LOAD_STATUS=0
bash "$BASE_DIR/infrastructure_test/run_load.sh" || LOAD_STATUS=$?

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
bash "$BASE_DIR/infrastructure_test/archive_evidence.sh" "$RUN_ID" || ARCHIVE_STATUS=$?

if (( LOAD_STATUS != 0 || ANALYSIS_STATUS != 0 || ARCHIVE_STATUS != 0 )); then
  echo "EXP-001 | INCOMPLETE OR FAILED" >&2
  echo "Load=$LOAD_STATUS Analysis=$ANALYSIS_STATUS Archive=$ARCHIVE_STATUS" >&2
  exit 1
fi

echo "=================================="
echo "EXP-001 | COMPLETED"
echo "Run ID: $RUN_ID"
echo "S3 and local evidence archived"
echo "=================================="
