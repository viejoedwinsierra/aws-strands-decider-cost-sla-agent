#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$BASE_DIR/config/experiment.env"

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
RUN_ID="${1:?Usage: archive_evidence.sh RUN_ID}"

[[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || {
  echo "ERROR: Invalid RUN_ID" >&2
  exit 1
}

: "${EVIDENCE_BUCKET:?}"

RESULTS_DIR="$BASE_DIR/results/$RUN_ID"
S3_PREFIX="s3://$EVIDENCE_BUCKET/experiments/exp001_capacity/results/$RUN_ID"

mkdir -p "$RESULTS_DIR"

# Download to Linux filesystem to avoid WSL2 /mnt/c timestamp errors.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  s3 cp "$S3_PREFIX/" "$TMP_DIR/" \
  --recursive --exclude "*" \
  --include "exp001_*.csv" \
  --include "metrics_normalized.json" \
  --include "sla_evaluation.json" \
  --include "run_manifest.json" \
  --no-progress

# Copy only evidence actually retrieved from S3.
# Avoid retaining stale local files from previous archive attempts.
shopt -s nullglob
evidence_files=(
  "$TMP_DIR"/exp001_*.csv
  "$TMP_DIR"/metrics_normalized.json
  "$TMP_DIR"/sla_evaluation.json
  "$TMP_DIR"/run_manifest.json
)

if (( ${#evidence_files[@]} == 0 )); then
  echo "ERROR: No evidence found in S3 for $RUN_ID" >&2
  exit 1
fi

if [[ "${REQUIRE_RUN_MANIFEST:-0}" == "1" &&
      ! -f "$TMP_DIR/run_manifest.json" ]]; then
  echo "ERROR: Required run_manifest.json missing from S3" >&2
  exit 1
fi

# Remove stale local evidence before restoring the S3 snapshot.
for name in \
  exp001_stats.csv \
  exp001_stats_history.csv \
  exp001_failures.csv \
  exp001_exceptions.csv \
  metrics_normalized.json \
  sla_evaluation.json \
  run_manifest.json \
  evidence_manifest.json; do
  rm -f "$RESULTS_DIR/$name"
done

RECOVERED_COUNT=0
for file in "${evidence_files[@]}"; do
  [[ -f "$file" ]] || continue
  cp "$file" "$RESULTS_DIR/"
  RECOVERED_COUNT=$((RECOVERED_COUNT + 1))
done

echo "Evidence files recovered: $RECOVERED_COUNT"

python3 - "$RESULTS_DIR" "$RUN_ID" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

directory = Path(sys.argv[1])
run_id = sys.argv[2]

expected = [
    "exp001_stats.csv",
    "exp001_stats_history.csv",
    "exp001_failures.csv",
    "exp001_exceptions.csv",
    "metrics_normalized.json",
    "sla_evaluation.json",
]

# New runs include a reproducible execution manifest.
if (directory / "run_manifest.json").is_file():
    expected.append("run_manifest.json")

files = {}
missing = []

for name in expected:
    path = directory / name
    if not path.is_file():
        missing.append(name)
        continue

    content = path.read_bytes()
    files[name] = {
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }

if not files:
    raise SystemExit("ERROR: No evidence files available")

archive_status = "COMPLETE" if not missing else "PARTIAL"

manifest = {
    "schema_version": "1.0",
    "experiment_id": "EXP-001",
    "run_id": run_id,
    "archived_at_utc": datetime.now(timezone.utc).isoformat(),
    "archive_status": archive_status,
    "missing_files": missing,
    "files": files,
}

(directory / "evidence_manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Manifest generated: {len(files)} files")
PY

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  s3 cp "$RESULTS_DIR/evidence_manifest.json" \
  "$S3_PREFIX/evidence_manifest.json" \
  --sse AES256 --no-progress

# Confirm that S3 contains exactly the manifest just generated.
TMP_MANIFEST="$(mktemp)"
trap 'rm -rf "$TMP_DIR"; rm -f "$TMP_MANIFEST"' EXIT

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  s3 cp "$S3_PREFIX/evidence_manifest.json" \
  "$TMP_MANIFEST" --no-progress

python3 - "$RESULTS_DIR" "$TMP_MANIFEST" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
remote_manifest = Path(sys.argv[2]).read_bytes()
local_manifest = (directory / "evidence_manifest.json").read_bytes()

if remote_manifest != local_manifest:
    raise SystemExit("ERROR: S3 manifest differs from local manifest")

manifest = json.loads(remote_manifest)
for name, metadata in manifest["files"].items():
    content = (directory / name).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != metadata["sha256"]:
        raise SystemExit(f"ERROR: SHA-256 mismatch: {name}")
    if len(content) != metadata["size_bytes"]:
        raise SystemExit(f"ERROR: Size mismatch: {name}")

print("ARCHIVE_VERIFICATION_PASSED")
print(f"Verified files: {len(manifest['files'])}")
PY

# Independently verify each archived object against S3.
python3 - "$RESULTS_DIR/evidence_manifest.json" "$S3_PREFIX" "$AWS_PROFILE" "$AWS_REGION" <<'VERIFY_REMOTE'
import hashlib
import json
import subprocess
import sys

manifest_path, prefix, profile, region = sys.argv[1:]
with open(manifest_path, encoding="utf-8") as file:
    manifest = json.load(file)

for name, metadata in manifest["files"].items():
    command = [
        "aws", "--profile", profile, "--region", region,
        "s3", "cp",
        prefix + "/" + name,
        "-",
        "--no-progress",
    ]
    result = subprocess.run(command, capture_output=True, check=True)
    actual = hashlib.sha256(result.stdout).hexdigest()
    if actual != metadata["sha256"]:
        raise SystemExit(f"ERROR: Remote SHA-256 mismatch: {name}")
    if len(result.stdout) != metadata["size_bytes"]:
        raise SystemExit(f"ERROR: Remote size mismatch: {name}")

print(f"S3_REMOTE_INTEGRITY_PASSED: {len(manifest['files'])} files")
VERIFY_REMOTE

echo "S3 archive: $S3_PREFIX/"
echo "Local backup: $RESULTS_DIR"
