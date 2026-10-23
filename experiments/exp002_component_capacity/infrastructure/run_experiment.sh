#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT/config/experiment.env"
[[ -f "$CONFIG" ]] || { echo 'Missing EXP-002 experiment.env' >&2; exit 1; }
set -a
source "$CONFIG"
set +a
: "${EVIDENCE_BUCKET:?}" "${WORKLOAD_INSTANCE_ID:?}" "${LOCUST_INSTANCE_ID:?}" "${LOCUST_BUNDLE_HASH:?}"
python3 "$ROOT/infrastructure/run_experiment.py"
