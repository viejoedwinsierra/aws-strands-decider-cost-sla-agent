#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -x .venv-agent/bin/python ]] || { echo 'Run scripts/setup_agent.sh first' >&2; exit 1; }
exec .venv-agent/bin/python -m src.agent.runner --sync "$@"
