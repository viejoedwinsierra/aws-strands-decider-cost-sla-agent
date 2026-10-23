#!/usr/bin/env bash
# EXP-002 environment contract adapted from EXP-001; no credential copying.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PROJECT_CONFIG="$BASE_DIR/config/project.env"
if [[ ! -f "$PROJECT_CONFIG" ]]; then
  echo "ERROR: Missing $PROJECT_CONFIG (copy project.env.example and review)" >&2
  exit 1
fi
set -a
source "$PROJECT_CONFIG"
set +a
: "${AWS_PROFILE:?}" "${AWS_REGION:?}" "${PROJECT_TAG:?}" "${EXPERIMENT_ID:?}" "${ENVIRONMENT:?}"
[[ "$EXPERIMENT_ID" == EXP-002 ]] || { echo 'ERROR: Expected EXP-002 project.env' >&2; exit 1; }
export AWS_DEFAULT_REGION="$AWS_REGION"
# Optional project-local credential source. Otherwise AWS CLI standard profiles.
CREDENTIALS_SOURCE="$BASE_DIR/config/aws_credentials.txt"
if [[ -s "$CREDENTIALS_SOURCE" ]]; then
  if grep -Fqx "[$AWS_PROFILE]" "$CREDENTIALS_SOURCE"; then
    export AWS_SHARED_CREDENTIALS_FILE="$CREDENTIALS_SOURCE"
  else
    echo "ERROR: Selected profile absent from project credentials source" >&2
    exit 1
  fi
fi
aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" --query Account --output text >/dev/null
printf '%s | AWS authentication validated (profile=%s, region=%s)\n' "$EXPERIMENT_ID" "$AWS_PROFILE" "$AWS_REGION"
