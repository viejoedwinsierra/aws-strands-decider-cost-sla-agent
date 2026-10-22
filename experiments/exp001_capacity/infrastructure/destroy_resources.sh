#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"
[[ -f "$CONFIG_FILE" ]] || { echo "Missing config: $CONFIG_FILE" >&2; exit 1; }
set -a
source "$CONFIG_FILE"
set +a
: "${AWS_PROFILE:?}" "${AWS_REGION:?}" "${PROJECT_TAG:?}" "${EXPERIMENT_ID:?}"
MODE="${1:---dry-run}"
case "$MODE" in
  --dry-run) exec python3 "$SCRIPT_DIR/python/destroy_resources.py" --dry-run ;;
  --execute)
    echo "WARNING: all EC2 instances and security groups tagged Project=$PROJECT_TAG, Experiment=$EXPERIMENT_ID will be deleted."
    echo "S3 evidence and shared network resources are retained. Root EBS volumes may be deleted."
    read -r -p "Type DELETE $EXPERIMENT_ID to proceed: " ANSWER
    [[ "$ANSWER" == "DELETE $EXPERIMENT_ID" ]] || { echo "Cancelled."; exit 1; }
    exec python3 "$SCRIPT_DIR/python/destroy_resources.py" --execute ;;
  *) echo "Usage: bash $0 [--dry-run|--execute]" >&2; exit 2 ;;
esac
