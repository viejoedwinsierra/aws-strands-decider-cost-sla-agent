#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

[[ -f "$CONFIG_FILE" ]] || {
  echo "ERROR: experiment.env not found" >&2
  exit 1
}

set -a
source "$CONFIG_FILE"
set +a

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

: "${EVIDENCE_BUCKET:?Missing EVIDENCE_BUCKET}"

echo "EXP-002 | Preparing dependencies"

prepare_wheels() {
  local component="$1"
  shift

  local wheel_dir
  wheel_dir="$(mktemp -d "${TMPDIR:-/tmp}/exp002-${component}-python311-XXXXXXXX")"
  local s3_prefix

  echo "Preparing ${component} wheels..."

  python3 -m pip download \
    --dest "$wheel_dir" \
    --only-binary=:all: \
    --python-version 3.11 \
    --implementation cp \
    --abi cp311 \
    --platform manylinux2014_x86_64 \
    "$@"

  python3 - "$wheel_dir" <<'PYLOCK'
import sys
from pathlib import Path
from pip._vendor.packaging.utils import parse_wheel_filename

directory = Path(sys.argv[1])
packages = {}

for wheel in sorted(directory.glob("*.whl")):
    name, version, _, _ = parse_wheel_filename(wheel.name)
    name = str(name).replace("_", "-").lower()
    if name in packages and packages[name] != str(version):
        raise SystemExit(f"ERROR: Conflicting versions for {name}")
    packages[name] = str(version)

if not packages:
    raise SystemExit("ERROR: No wheels found")

(directory / "requirements.lock").write_text(
    "".join(f"{name}=={version}\n" for name, version in sorted(packages.items()))
)
lock = (directory / "requirements.lock").read_text().splitlines()
assert len(lock) == len(packages) and all(line.count("==") == 1 for line in lock)
print(f"EXP-002 | Locked {len(packages)} packages")
PYLOCK

  (
    cd "$wheel_dir"
    sha256sum -- *.whl requirements.lock > SHA256SUMS.txt
    sha256sum -c SHA256SUMS.txt
  )

  local bundle_hash
  bundle_hash="$(sha256sum "$wheel_dir/SHA256SUMS.txt" | cut -d ' ' -f 1)"

  s3_prefix="s3://${EVIDENCE_BUCKET}/dependencies/exp002/${component}/python311-linux-x86_64/${bundle_hash}/"

  echo "EXP-002 | ${component} bundle SHA-256: ${bundle_hash}"
  echo "Uploading ${component} wheels to S3..."

  aws s3 sync \
    "$wheel_dir/" \
    "$s3_prefix" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --exclude "*" \
    --include "*.whl" \
    --include "SHA256SUMS.txt" \
    --include "requirements.lock" \
    --sse AES256

  local hash_key
  case "$component" in
    fastapi) hash_key="FASTAPI_BUNDLE_HASH" ;;
    locust)  hash_key="LOCUST_BUNDLE_HASH" ;;
    *) echo "ERROR: Unsupported component: $component" >&2; return 1 ;;
  esac

  CONFIG_FILE="$CONFIG_FILE" HASH_KEY="$hash_key" BUNDLE_HASH="$bundle_hash" python3 - <<'PYCONFIG'
import os
import re
from pathlib import Path

p = Path(os.environ["CONFIG_FILE"])
key = os.environ["HASH_KEY"]
value = os.environ["BUNDLE_HASH"]

if not re.fullmatch(r"[0-9a-f]{64}", value):
    raise SystemExit("ERROR: Invalid SHA-256 bundle hash")

lines = p.read_text().splitlines()
out = []
found = False

for line in lines:
    if line.startswith(key + "="):
        if not found:
            out.append(f"{key}={value}")
            found = True
    else:
        out.append(line)

if not found:
    out.append(f"{key}={value}")

tmp = p.with_suffix(".tmp")
tmp.write_text("\n".join(out) + "\n")
tmp.replace(p)

print(f"EXP-002 | {key} saved")
PYCONFIG

  echo "${component} dependencies ready: $s3_prefix"
}

prepare_wheels locust \
  'locust==2.46.7' \
  'typing-extensions>=4.6.0'

prepare_wheels fastapi \
  'fastapi==0.115.6' \
  'uvicorn==0.34.0' \
  'psycopg[binary]==3.2.6'

echo "EXP-002 | Dependency preparation completed."
