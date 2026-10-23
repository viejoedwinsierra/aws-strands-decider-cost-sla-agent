#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
MODE="${1:-}"
case "$MODE" in
  deploy|resume)
    source "$SCRIPT_DIR/load_environment.sh"
    exec bash "$SCRIPT_DIR/deploy.sh" "$MODE" ;;
  verify)
    source "$SCRIPT_DIR/load_environment.sh"
    exec bash "$SCRIPT_DIR/verify_all.sh" ;;
  run)
    shift
    if [[ "${1:-}" != '--dry-run' ]]; then source "$SCRIPT_DIR/load_environment.sh"; fi
    exec bash "$BASE_DIR/infrastructure_test/run.sh" "$@" ;;
  *) echo 'ERROR: Use deploy, resume, verify or run [--dry-run|--execute]' >&2; exit 2 ;;
esac
