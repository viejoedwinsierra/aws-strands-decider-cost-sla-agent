#!/usr/bin/env bash
# EXP-001 campaign entrypoint. Runs infrastructure checks once.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG="$BASE_DIR/config/experiment.env"
[[ -f "$CONFIG" ]] || { echo "ERROR: Missing $CONFIG" >&2; exit 1; }
set -a
source "$CONFIG"
set +a
export AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
: "${EVIDENCE_BUCKET:?}"
: "${PROJECT_TAG:?}"
: "${EXPERIMENT_ID:?}"
: "${ENVIRONMENT:?}"
CONFIG_YAML="$BASE_DIR/config/test_sequence.yml"
# Explicit selection; the historical campaign remains the default.
RUN_ARGS=()
while (( $# )); do
  case "$1" in
    --sequence-config)
      (( $# >= 2 )) || { echo "ERROR: --sequence-config needs a path" >&2; exit 2; }
      CONFIG_YAML="$2"; shift 2 ;;
    *) RUN_ARGS+=("$1"); shift ;;
  esac
done
set -- "${RUN_ARGS[@]}"
[[ -f "$CONFIG_YAML" ]] || { echo "ERROR: Sequence YAML not found: $CONFIG_YAML" >&2; exit 2; }
DETAIL_SCRIPT="$BASE_DIR/../shared/monitoring/detailed_monitoring.py"
LINUX_SCRIPT="$BASE_DIR/../shared/monitoring/linux_ssm.py"
[[ -f "$DETAIL_SCRIPT" ]] || { echo "ERROR: Missing $DETAIL_SCRIPT" >&2; exit 1; }
# Phase B: persistent Linux cron collector plus per-campaign S3 evidence.
export CLOUDWATCH_PERIOD_SECONDS=60

# Dry run validates YAML without contacting AWS or performing validations.
if [[ "${1:-}" == "--dry-run" ]]; then
  exec python3 "$SCRIPT_DIR/python/sequence_runner.py" --config "$CONFIG_YAML" "$@"
fi
# Validate YAML before touching AWS.
python3 "$SCRIPT_DIR/python/sequence_runner.py" --config "$CONFIG_YAML" --dry-run "${@}" >/dev/null
CAMPAIGN_INVENTORY="$(mktemp)"
# Restore detailed monitoring even when a test or finalization fails.
DETAIL_ENABLED=0
DETAIL_RESTORE_STATUS=0
DETAIL_STATE=""
restore_detail() {
  if (( DETAIL_ENABLED == 1 )); then
    echo "EXP-001 | Restoring EC2 monitoring configuration"
    if python3 "$DETAIL_SCRIPT" restore --execute \
      --profile "$AWS_PROFILE" --region "$AWS_REGION" \
      --project "$PROJECT_TAG" --experiment "$EXPERIMENT_ID" \
      --environment "$ENVIRONMENT" --state-file "$DETAIL_STATE"; then
      DETAIL_ENABLED=0
      echo "DETAIL_MONITORING_RESTORED: campaign=${CAMPAIGN_ID:-unknown}"
    else
      DETAIL_RESTORE_STATUS=1
      echo "ERROR: Detailed Monitoring restoration failed; recover using $DETAIL_STATE" >&2
      return 1
    fi
  fi
}
cleanup_campaign() {
  local rc=$?
  trap - EXIT INT TERM
  if (( DETAIL_ENABLED == 1 )); then
    restore_detail || rc=1
  fi
  rm -f "$CAMPAIGN_INVENTORY"
  exit "$rc"
}
trap cleanup_campaign EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 "$BASE_DIR/../shared/python/discover_instances.py" \
  --project "$PROJECT_TAG" --experiment "$EXPERIMENT_ID" \
  --environment "$ENVIRONMENT" --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" --output "$CAMPAIGN_INVENTORY"
mapfile -t INSTANCE_IDS < <(python3 "$SCRIPT_DIR/python/resolve_instance_roles.py" "$CAMPAIGN_INVENTORY")
(( ${#INSTANCE_IDS[@]} >= 2 )) || { echo "ERROR: Missing EC2 roles" >&2; exit 1; }
export HTTP_INSTANCE_ID="${INSTANCE_IDS[0]}"
export LOCUST_INSTANCE_ID="${INSTANCE_IDS[1]}"
echo "EXP-001 | Preflight once: HTTP=$HTTP_INSTANCE_ID LOCUST=$LOCUST_INSTANCE_ID"
bash "$BASE_DIR/infrastructure/verify_security.sh"
bash "$BASE_DIR/infrastructure/verify.sh"
bash "$BASE_DIR/infrastructure/verify_locust.sh"
bash "$BASE_DIR/infrastructure/verify_network.sh"
echo "EXP-001 | Preflight complete; starting YAML sequence"
# Freeze campaign identity and inventory before collecting metrics.
CAMPAIGN_ID="exp001_$(date -u +%Y%m%dT%H%M%S%NZ)"
CAMPAIGN_DIR="$BASE_DIR/results/campaigns/$CAMPAIGN_ID"
mkdir -p "$CAMPAIGN_DIR"
cp "$CAMPAIGN_INVENTORY" "$CAMPAIGN_DIR/ec2_inventory.json"
DETAIL_STATE="$CAMPAIGN_DIR/detailed_monitoring_state.json"
# Mark recovery as necessary before the first write call; the controller
# journals its per-instance intentions before modifying AWS.
DETAIL_ENABLED=1
echo "DETAIL_MONITORING_ENABLING: campaign=$CAMPAIGN_ID instances=${INSTANCE_IDS[*]}"
python3 "$DETAIL_SCRIPT" enable --execute \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --project "$PROJECT_TAG" --experiment "$EXPERIMENT_ID" \
  --environment "$ENVIRONMENT" --state-file "$DETAIL_STATE"
echo "DETAIL_MONITORING_ENABLED: campaign=$CAMPAIGN_ID instances=${INSTANCE_IDS[*]}"
# Do not begin PRE unless activation was verified by the controller.

echo "EXP-001 | Installing persistent Linux cron monitors"
python3 "$LINUX_SCRIPT" install \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --http-id "$HTTP_INSTANCE_ID" --locust-id "$LOCUST_INSTANCE_ID"
PRE_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "EXP-001 | Campaign PRE: $PRE_START (60s)"
sleep 60
PRE_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOAD_STATUS=0
python3 "$SCRIPT_DIR/python/sequence_runner.py" --config "$CONFIG_YAML" --campaign-id "$CAMPAIGN_ID" "$@" || LOAD_STATUS=$?
POST_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "EXP-001 | Campaign POST: $POST_START (60s)"
sleep 60
POST_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LINUX_STATUS=0
python3 "$LINUX_SCRIPT" collect \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --http-id "$HTTP_INSTANCE_ID" --locust-id "$LOCUST_INSTANCE_ID" \
  --campaign-id "$CAMPAIGN_ID" --start "$PRE_START" --end "$POST_END" \
  --bucket "$EVIDENCE_BUCKET" --output-dir "$CAMPAIGN_DIR/linux" \
  || LINUX_STATUS=$?
FINALIZE_STATUS=0
python3 "$SCRIPT_DIR/python/finalize_campaign.py" \
  --campaign-id "$CAMPAIGN_ID" --pre-start "$PRE_START" --pre-end "$PRE_END" \
  --post-start "$POST_START" --post-end "$POST_END" \
  --inventory "$CAMPAIGN_DIR/ec2_inventory.json" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --bucket "$EVIDENCE_BUCKET" --period "${CLOUDWATCH_PERIOD_SECONDS:-300}" \
  || FINALIZE_STATUS=$?
# Normal path restores before reporting success. The EXIT trap is fallback.
restore_detail || DETAIL_RESTORE_STATUS=1
# Preserve the complete enable/restore journal in mandatory S3 evidence.
STATE_UPLOAD_STATUS=0
if [[ -f "$DETAIL_STATE" ]]; then
  aws s3 cp "$DETAIL_STATE" \
    "s3://${EVIDENCE_BUCKET}/experiments/exp001_capacity/results/campaigns/${CAMPAIGN_ID}/detailed_monitoring_state.json" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" --sse AES256 --no-progress \
    || STATE_UPLOAD_STATUS=1
else
  STATE_UPLOAD_STATUS=1
fi
QUALITY_STATUS=0
if (( LINUX_STATUS == 0 && FINALIZE_STATUS == 0 && DETAIL_RESTORE_STATUS == 0 && STATE_UPLOAD_STATUS == 0 )); then
  python3 "$BASE_DIR/../shared/monitoring/validate_campaign.py" \
    --campaign-id "$CAMPAIGN_ID" --campaign-dir "$CAMPAIGN_DIR" \
    --bucket "$EVIDENCE_BUCKET" --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --pre-start "$PRE_START" --pre-end "$PRE_END" \
    --post-start "$POST_START" --post-end "$POST_END" \
    --http-id "$HTTP_INSTANCE_ID" --locust-id "$LOCUST_INSTANCE_ID" || QUALITY_STATUS=$?
else
  QUALITY_STATUS=1
  echo "EVIDENCE_QUALITY_SKIPPED: upstream evidence or restoration failed" >&2
fi
if (( LOAD_STATUS != 0 || LINUX_STATUS != 0 || FINALIZE_STATUS != 0 || DETAIL_RESTORE_STATUS != 0 || STATE_UPLOAD_STATUS != 0 || QUALITY_STATUS != 0 )); then
  echo "EXP-001 | INCOMPLETE: Load=$LOAD_STATUS Linux=$LINUX_STATUS Observability=$FINALIZE_STATUS Restore=$DETAIL_RESTORE_STATUS StateUpload=$STATE_UPLOAD_STATUS Quality=$QUALITY_STATUS" >&2
  exit 1
fi
echo "EXP-001 | COMPLETED: $CAMPAIGN_ID"
