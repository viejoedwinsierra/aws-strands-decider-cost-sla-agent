#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/load_environment.sh"

MODE="${1:-run}"

case "$MODE" in
    deploy)
        echo "$EXPERIMENT_ID | Starting infrastructure deployment"
        exec bash "$SCRIPT_DIR/deploy.sh"
        ;;
    run)
        echo "$EXPERIMENT_ID | Starting experiment execution"
        exec bash "$BASE_DIR/infrastructure_test/run.sh"
        ;;
    *)
        echo "$EXPERIMENT_ID | ERROR: Supported modes: deploy, run" >&2
        exit 1
        ;;
esac