#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
[[ -f "$CONFIG_FILE" ]] || { echo "Missing config: $CONFIG_FILE" >&2; exit 1; }
set -a
source "$CONFIG_FILE"
set +a
: "${AWS_PROFILE:?}" "${AWS_REGION:?}" "${PROJECT_TAG:?}" "${EXPERIMENT_ID:?}" "${HTTP_INSTANCE_ID:?}" "${LOCUST_INSTANCE_ID:?}"
[[ "$EXPERIMENT_ID" == "EXP-001" ]] || { echo "Refusing: expected EXP-001" >&2; exit 1; }
MODE="${1:---dry-run}"
case "$MODE" in
  --dry-run) exec python3 "$SCRIPT_DIR/python/destroy_exp001.py" --dry-run ;;
  --execute)
    echo "WARNING: permanently terminate EC2 HTTP=$HTTP_INSTANCE_ID and Locust=$LOCUST_INSTANCE_ID"
    echo "S3 evidence bucket and shared networking will NOT be deleted."
    read -r -p "Type TERMINATE EXP-001 to proceed: " ANSWER
    [[ "$ANSWER" == "TERMINATE EXP-001" ]] || { echo "Cancelled."; exit 1; }
    exec python3 "$SCRIPT_DIR/python/destroy_exp001.py" --execute ;;
  *) echo "Usage: bash $0 [--dry-run|--execute]" >&2; exit 2 ;;
esac
