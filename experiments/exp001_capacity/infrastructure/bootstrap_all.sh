#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

MODE="${1:-run}"
if [[ "$MODE" == "deploy" ]]; then
  echo "EXP-001 | Automated Deployment"

  echo "[1/8] Prepare S3"
  bash "$SCRIPT_DIR/create_bucket.sh"

  echo "[2/8] Prepare Locust dependencies"
  bash "$SCRIPT_DIR/prepare_dependencies.sh"

  echo "[3/8] Provision HTTP EC2"
  INSTANCE_ROLE=http-server bash "$SCRIPT_DIR/provision.sh"

  echo "[4/8] Deploy HTTP"
  set -a
  source "$BASE_DIR/config/experiment.env"
  set +a
  INSTANCE_ID="$HTTP_INSTANCE_ID" bash "$SCRIPT_DIR/deploy_http.sh"

  echo "[5/8] Provision Locust EC2"
  INSTANCE_ROLE=load-generator bash "$SCRIPT_DIR/provision.sh"

  echo "[6/8] Deploy Locust"
  set -a
  source "$BASE_DIR/config/experiment.env"
  set +a
  : "${HTTP_INSTANCE_ID:?Missing HTTP_INSTANCE_ID}"
  : "${LOCUST_INSTANCE_ID:?Missing LOCUST_INSTANCE_ID}"
  : "${EVIDENCE_BUCKET:?Missing EVIDENCE_BUCKET}"
  bash "$SCRIPT_DIR/deploy_locust.sh"

  echo "[7/8] Configure private network"
  bash "$SCRIPT_DIR/configure_network.sh"

  echo "[8/8] Verify infrastructure"
  bash "$SCRIPT_DIR/verify_security.sh"
  bash "$SCRIPT_DIR/verify.sh"
  bash "$SCRIPT_DIR/verify_locust.sh"
  bash "$SCRIPT_DIR/verify_network.sh"

  echo "EXP-001 | DEPLOYMENT COMPLETED"
  exit 0
fi

[[ "$MODE" == "run" ]] || {
  echo "ERROR: Supported modes: deploy, run" >&2
  exit 1
}

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
bash "$SCRIPT_DIR/run_load.sh" || LOAD_STATUS=$?

echo "[4/5] Normalize and evaluate SLA"
ANALYSIS_STATUS=0
STATS_FILE="$BASE_DIR/results/$RUN_ID/exp001_stats.csv"

if [[ -s "$STATS_FILE" ]]; then
  bash "$SCRIPT_DIR/analyze_results.sh" "$RUN_ID" || ANALYSIS_STATUS=$?
else
  echo "WARNING: No statistics available; SLA cannot be evaluated" >&2
  ANALYSIS_STATUS=1
fi

echo "[5/5] Archive and verify evidence"
ARCHIVE_STATUS=0
bash "$SCRIPT_DIR/archive_evidence.sh" "$RUN_ID" || ARCHIVE_STATUS=$?

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
