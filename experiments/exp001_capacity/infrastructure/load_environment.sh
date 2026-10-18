#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$BASE_DIR/config"

# ==========================================
# 1. Load general project configuration
# ==========================================

PROJECT_CONFIG="$CONFIG_DIR/project.env"

if [[ ! -f "$PROJECT_CONFIG" ]]; then
    echo "ERROR: Project configuration not found: $PROJECT_CONFIG" >&2
    exit 1
fi

set -a
source "$PROJECT_CONFIG"
set +a

: "${AWS_PROFILE:?AWS_PROFILE is required}"
: "${AWS_REGION:?AWS_REGION is required}"
: "${EXPERIMENT_ID:?EXPERIMENT_ID is required}"
: "${PROJECT_TAG:?PROJECT_TAG is required}"

export AWS_PROFILE
export AWS_REGION
export AWS_DEFAULT_REGION="$AWS_REGION"
export EXPERIMENT_ID
export PROJECT_TAG

echo "$EXPERIMENT_ID | Project configuration loaded"
echo "$EXPERIMENT_ID | AWS profile: $AWS_PROFILE"
echo "$EXPERIMENT_ID | AWS region: $AWS_REGION"

# ==========================================
# 2. Synchronize AWS credentials
# ==========================================

CREDENTIALS_SOURCE="$CONFIG_DIR/aws_credentials.txt"
CREDENTIALS_TARGET="$HOME/.aws/credentials"

if [[ ! -s "$CREDENTIALS_SOURCE" ]]; then
    echo "$EXPERIMENT_ID | ERROR: AWS credentials file missing or empty" >&2
    exit 1
fi

# Verify that the selected profile exists in the source
if ! grep -Fqx "[$AWS_PROFILE]" "$CREDENTIALS_SOURCE"; then
    echo "$EXPERIMENT_ID | ERROR: AWS profile not found in credentials source" >&2
    exit 1
fi

# Use the project credentials file directly.
# This avoids overwriting other AWS CLI profiles.
export AWS_SHARED_CREDENTIALS_FILE="$CREDENTIALS_SOURCE"

echo "$EXPERIMENT_ID | AWS credentials synchronized"

# ==========================================
# 3. Validate AWS authentication
# ==========================================

if ! aws sts get-caller-identity \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --query 'Account' \
    --output text >/dev/null; then

    echo "$EXPERIMENT_ID | ERROR: AWS authentication failed" >&2
    exit 1
fi

echo "$EXPERIMENT_ID | AWS authentication validated"
