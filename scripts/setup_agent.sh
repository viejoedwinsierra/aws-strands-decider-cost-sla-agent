#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${INFRAVITA_PYTHON:-$HOME/.venvs/infravita-decider/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "INFRAVITA_PYTHON_NOT_FOUND: $PYTHON" >&2
  exit 1
fi

"$PYTHON" - <<'CHECK'
import importlib.util

required = ("yaml", "torch", "transformers", "strands_decider")
missing = [name for name in required if importlib.util.find_spec(name) is None]

if missing:
    raise SystemExit("MISSING_DEPENDENCIES: " + ", ".join(missing))

print("EXISTING_ENVIRONMENT_VALIDATED")
CHECK
