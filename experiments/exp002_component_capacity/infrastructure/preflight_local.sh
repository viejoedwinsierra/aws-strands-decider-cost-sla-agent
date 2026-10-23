#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
BASE=experiments/exp002_component_capacity
printf 'EXP-002 LOCAL PREFLIGHT (no AWS operations)\n'
python3 - "$BASE" <<'PY'
from pathlib import Path
import ast, sys
base=Path(sys.argv[1])
required=['infrastructure/bootstrap_all.sh','infrastructure/provision.sh','infrastructure/deploy_postgresql.sh','infrastructure/deploy_fastapi.sh','infrastructure/deploy_locust.sh','infrastructure/verify.sh','infrastructure/verify_security.sh','infrastructure/verify_network.sh','scripts/locustfile.py','exp002_fastapi/app/main.py']
missing=[x for x in required if not (base/x).is_file()]
if missing: raise SystemExit('MISSING_FILES: '+', '.join(missing))
for path in base.rglob('*.py'):
    if 'dependencies' in path.parts: continue
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
print('REQUIRED_FILES_AND_PYTHON_SYNTAX_VALID')
PY
for script in "$BASE"/infrastructure/*.sh; do bash -n "$script"; done
printf 'SHELL_SYNTAX_VALID\n'
python3 "$BASE/tests/test_local_reproducibility.py"
printf 'EXP002_LOCAL_PREFLIGHT_COMPLETE\n'
