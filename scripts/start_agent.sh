#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${INFRAVITA_PYTHON:-$HOME/.venvs/infravita-decider/bin/python}"

INSTALL_MODE="none"
WITH_DEV=false
OFFLINE=false
CHECK_ONLY=false
INFER=false
EXTRA_ARGS=()

while (($#)); do
  case "$1" in
    --check) CHECK_ONLY=true ;;
    --install-missing) INSTALL_MODE="missing" ;;
    --install-all) INSTALL_MODE="all" ;;
    --with-dev) WITH_DEV=true ;;
    --offline) OFFLINE=true ;;
    --infer) INFER=true ;;
    *) EXTRA_ARGS+=("$1") ;;
  esac
  shift
done

if [[ ! -x "$PYTHON" ]]; then
  echo "INFRAVITA_ENVIRONMENT_NOT_FOUND: $PYTHON" >&2
  exit 1
fi

if [[ "$OFFLINE" == true ]]; then
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
  export PIP_NO_INDEX=1
fi

SETUP_ARGS=(--check)

if [[ "$INSTALL_MODE" == "missing" ]]; then
  SETUP_ARGS=(--install-missing)
elif [[ "$INSTALL_MODE" == "all" ]]; then
  SETUP_ARGS=(--install-all)
fi

if [[ "$WITH_DEV" == true ]]; then
  SETUP_ARGS+=(--with-dev)
fi

if [[ "$OFFLINE" == true ]]; then
  SETUP_ARGS+=(--offline)
fi

# setup_agent.sh must implement these options in Delivery 6.
bash scripts/setup_agent.sh "${SETUP_ARGS[@]}"

if [[ "$CHECK_ONLY" == true ]]; then
  echo "INFRAVITA_CHECK_COMPLETED"
  exit 0
fi

if [[ "$INFER" == true ]]; then
  exec "$PYTHON" -m src.agent.official_integration \
    --infer "${EXTRA_ARGS[@]}"
fi

exec "$PYTHON" -m src.agent.runner --source local "${EXTRA_ARGS[@]}"
