#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Missing configuration: $CONFIG_FILE" >&2
    exit 1
fi

set -a
source "$CONFIG_FILE"
set +a

: "${AWS_PROFILE:?AWS_PROFILE is required}"
: "${AWS_REGION:?AWS_REGION is required}"
: "${INSTANCE_ID:?INSTANCE_ID is required}"
: "${PROJECT_TAG:?PROJECT_TAG is required}"
: "${EXPERIMENT_ID:?EXPERIMENT_ID is required}"

echo "EXP-001 | Cleanup dry-run"

INSTANCE_INFO=$(aws ec2 describe-instances \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].[State.Name,Tags[?Key==`Project`].Value | [0],Tags[?Key==`Experiment`].Value | [0]]' \
    --output text)

read -r STATE ACTUAL_PROJECT ACTUAL_EXPERIMENT <<< "$INSTANCE_INFO"

if [[ "$ACTUAL_PROJECT" != "$PROJECT_TAG" ||
      "$ACTUAL_EXPERIMENT" != "$EXPERIMENT_ID" ]]; then
    echo "ERROR: Instance ownership validation failed." >&2
    exit 1
fi

echo "Instance: $INSTANCE_ID"
echo "State: $STATE"
echo "Ownership: validated"
echo "DRY-RUN: No resources modified or deleted."
