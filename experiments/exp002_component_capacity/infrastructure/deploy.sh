#!/usr/bin/env bash
# V5: use the EXP-001 stage order; reuse EXP-002's existing official scripts.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
MODE="${1:-deploy}"
[[ "$MODE" == deploy || "$MODE" == resume ]] || { echo 'Expected deploy or resume' >&2; exit 2; }
: "${AWS_PROFILE:?Use bootstrap_all.sh}" "${EXPERIMENT_ID:?}"
STATE_DIR="$BASE_DIR/results/deployment"
mkdir -p "$STATE_DIR"
JOURNAL="$STATE_DIR/latest.tsv"
touch "$JOURNAL"
CURRENT_STAGE=initialization
on_exit() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\tFAIL\t%s\t%s\n' "$(date -u +%FT%TZ)" "$CURRENT_STAGE" "$rc" >> "$JOURNAL"
    echo "EXP-002 | FAILED at $CURRENT_STAGE (exit=$rc). Run bootstrap_all.sh resume after diagnosis." >&2
  fi
}
trap on_exit EXIT
stage() {
  CURRENT_STAGE="$1"
  shift
  printf '%s\tSTART\t%s\n' "$(date -u +%FT%TZ)" "$CURRENT_STAGE" >> "$JOURNAL"
  echo "EXP-002 | $CURRENT_STAGE"
  "$@"
  printf '%s\tPASS\t%s\n' "$(date -u +%FT%TZ)" "$CURRENT_STAGE" >> "$JOURNAL"
}
refresh_config() {
  if [[ -f "$BASE_DIR/config/experiment.env" ]]; then
    set -a
    source "$BASE_DIR/config/experiment.env"
    set +a
  fi
}
# A resume is driven by live checks, not stale local success markers.
# A full deploy still invokes official provisioning scripts (they discover tagged EC2).
if [[ "$MODE" == resume ]]; then
  refresh_config
  if [[ -n "${WORKLOAD_INSTANCE_ID:-}" && -n "${LOCUST_INSTANCE_ID:-}" ]] && \
    bash "$SCRIPT_DIR/verify_all.sh" >/dev/null 2>&1; then
    echo 'EXP-002 | Existing infrastructure healthy; no redeployment necessary'
    printf '%s\tPASS\talready-healthy\n' "$(date -u +%FT%TZ)" >> "$JOURNAL"
    exit 0
  fi
fi
stage s3 bash "$SCRIPT_DIR/create_bucket.sh"
refresh_config
stage dependencies bash "$SCRIPT_DIR/prepare_dependencies.sh"
stage workload-provision env INSTANCE_ROLE=workload-server bash "$SCRIPT_DIR/provision.sh"
refresh_config
: "${WORKLOAD_INSTANCE_ID:?Missing workload instance ID}"
# PostgreSQL deployment is idempotent; when healthy avoid reinstalling on resume.
if [[ "$MODE" == resume ]] && bash "$SCRIPT_DIR/verify.sh" >/dev/null 2>&1; then
  echo 'EXP-002 | Workload already healthy; skipping PostgreSQL and FastAPI deployment'
else
  stage postgresql bash "$SCRIPT_DIR/deploy_postgresql.sh"
  stage fastapi bash "$SCRIPT_DIR/deploy_fastapi.sh"
fi
stage locust-provision env INSTANCE_ROLE=load-generator bash "$SCRIPT_DIR/provision.sh"
refresh_config
: "${LOCUST_INSTANCE_ID:?Missing Locust instance ID}" "${EVIDENCE_BUCKET:?Missing evidence bucket}"
if [[ "$MODE" == resume ]] && bash "$SCRIPT_DIR/verify_locust.sh" >/dev/null 2>&1; then
  echo 'EXP-002 | Locust healthy; skipping redeployment'
else
  stage locust bash "$SCRIPT_DIR/deploy_locust.sh"
fi
stage network bash "$SCRIPT_DIR/configure_network.sh"
stage verify bash "$SCRIPT_DIR/verify_all.sh"
echo 'EXP-002 | DEPLOYMENT COMPLETED'
