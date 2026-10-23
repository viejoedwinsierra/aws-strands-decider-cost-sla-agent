#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m venv "$ROOT/.venv-agent"
"$ROOT/.venv-agent/bin/python" -m pip install --upgrade pip
"$ROOT/.venv-agent/bin/python" -m pip install -e "$ROOT"
if [[ "${INSTALL_DECIDER:-0}" == "1" ]]; then
  "$ROOT/.venv-agent/bin/python" -m pip install -e "$ROOT[decider]"
fi
printf 'SETUP_COMPLETE\n'
