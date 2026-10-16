#!/usr/bin/env bash
# EXP-001: one-command idempotent recovery.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export PROJECT_TAG="${PROJECT_TAG:-AWS-Cost-SLA-Decision-Agent}"
export EXPERIMENT_ID="${EXPERIMENT_ID:-EXP-001}"

printf 'EXP-001 | Bootstrap | profile=%s region=%s\n' "$AWS_PROFILE" "$AWS_REGION"
INSTANCE_ID="$(bash "$SCRIPT_DIR/provision.sh")"
[[ "$INSTANCE_ID" =~ ^i-[0-9a-f]+$ ]] || { echo "ERROR: Invalid instance ID: $INSTANCE_ID" >&2; exit 1; }
export INSTANCE_ID
printf 'EC2 lista: %s\n' "$INSTANCE_ID"
bash "$SCRIPT_DIR/deploy_http.sh"
bash "$SCRIPT_DIR/verify.sh"
printf 'EXP-001 recuperado: %s\n' "$INSTANCE_ID"
