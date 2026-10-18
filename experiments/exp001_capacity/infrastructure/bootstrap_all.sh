#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

MODE="${1:-run}"
case "$MODE" in
  deploy) exec bash "$SCRIPT_DIR/deploy.sh" ;;
  run) exec bash "$BASE_DIR/infrastructure_test/run.sh" ;;
  *) echo "ERROR: Supported modes: deploy, run" >&2; exit 1 ;;
esac
