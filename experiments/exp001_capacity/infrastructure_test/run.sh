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
# Dry run validates YAML without contacting AWS or performing validations.
if [[ "${1:-}" == "--dry-run" ]]; then
  exec python3 "$SCRIPT_DIR/python/sequence_runner.py" --config "$CONFIG_YAML" "$@"
fi
# Validate YAML before touching AWS.
python3 "$SCRIPT_DIR/python/sequence_runner.py" --config "$CONFIG_YAML" --dry-run "${@}" >/dev/null
CAMPAIGN_INVENTORY="$(mktemp)"
trap 'rm -f "$CAMPAIGN_INVENTORY"' EXIT
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
FINALIZE_STATUS=0
python3 "$SCRIPT_DIR/python/finalize_campaign.py" \
  --campaign-id "$CAMPAIGN_ID" --pre-start "$PRE_START" --pre-end "$PRE_END" \
  --post-start "$POST_START" --post-end "$POST_END" \
  --inventory "$CAMPAIGN_DIR/ec2_inventory.json" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --bucket "$EVIDENCE_BUCKET" --period "${CLOUDWATCH_PERIOD_SECONDS:-300}" \
  || FINALIZE_STATUS=$?
if (( LOAD_STATUS != 0 || FINALIZE_STATUS != 0 )); then
  echo "EXP-001 | INCOMPLETE: Load=$LOAD_STATUS Observability=$FINALIZE_STATUS" >&2
  exit 1
fi
echo "EXP-001 | COMPLETED: $CAMPAIGN_ID"
