#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Reuse the four official verification components, same pattern as EXP-001.
for check in verify_security.sh verify.sh verify_locust.sh verify_network.sh; do
  echo "EXP-002 | Checking $check"
  bash "$SCRIPT_DIR/$check"
done
echo 'EXP002_FULL_VERIFICATION_PASS'
