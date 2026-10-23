#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${INFRAVITA_PYTHON:-$HOME/.venvs/infravita-decider/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "INFRAVITA_PYTHON_NOT_FOUND: $PYTHON" >&2
  exit 1
fi

exec "$PYTHON" -m src.agent.runner --source local "$@"
