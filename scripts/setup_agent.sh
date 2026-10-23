#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${INFRAVITA_PYTHON:-$HOME/.venvs/infravita-decider/bin/python}"

MODE="check"
OFFLINE=false
WITH_DEV=false

while (($#)); do
  case "$1" in
    --check) MODE="check" ;;
    --install-missing) MODE="install-missing" ;;
    --install-all) MODE="install-all" ;;
    --offline) OFFLINE=true ;;
    --with-dev) WITH_DEV=true ;;
    *)
      echo "UNKNOWN_OPTION: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [[ ! -x "$PYTHON" ]]; then
  echo "INFRAVITA_PYTHON_NOT_FOUND: $PYTHON" >&2
  exit 1
fi

if [[ "$OFFLINE" == true ]]; then
  export PIP_NO_INDEX=1
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
fi

check_dependencies() {
  "$PYTHON" - "$WITH_DEV" <<'CHECK'
import importlib.metadata as metadata
import sys

from packaging.requirements import Requirement

requirements = [
    "PyYAML>=6,<7",
    "strands-decider==0.1.0",
    "transformers==5.20.1",
    "accelerate==1.15.0",
]

if sys.argv[1] == "true":
    requirements.append("pytest")

missing = []

for specification in requirements:
    requirement = Requirement(specification)
    try:
        version = metadata.version(requirement.name)
        if version not in requirement.specifier:
            missing.append(specification)
            print(f"INCOMPATIBLE: {requirement.name}=={version}")
        else:
            print(f"VALID: {requirement.name}=={version}")
    except metadata.PackageNotFoundError:
        missing.append(specification)
        print(f"MISSING: {specification}")

try:
    torch_version = metadata.version("torch")
    print(f"TORCH_AVAILABLE: {torch_version}")
except metadata.PackageNotFoundError:
    missing.append("torch")
    print("TORCH_MISSING")

if missing:
    print("DEPENDENCY_VALIDATION_FAILED")
    sys.exit(1)

print("EXISTING_ENVIRONMENT_VALIDATED")
CHECK
}

if [[ "$MODE" == "check" ]]; then
  check_dependencies
  exit $?
fi

# Never install or replace PyTorch automatically.
if ! "$PYTHON" -c "import torch" >/dev/null 2>&1; then
  echo "TORCH_REQUIRED: manual review before installation" >&2
  exit 1
fi

PIP_ARGS=(install)

if [[ "$MODE" == "install-missing" ]]; then
  PIP_ARGS+=(--upgrade-strategy only-if-needed)
fi

PIP_ARGS+=(
  "PyYAML>=6,<7"
  "strands-decider==0.1.0"
  "transformers==5.20.1"
  "accelerate==1.15.0"
)

if [[ "$WITH_DEV" == true ]]; then
  PIP_ARGS+=("pytest")
fi

"$PYTHON" -m pip "${PIP_ARGS[@]}"

check_dependencies
