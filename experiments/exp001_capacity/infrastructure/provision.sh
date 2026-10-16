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

echo "EXP-001 | Safe infrastructure provisioning"
echo "Checking existing instance: $INSTANCE_ID"

aws ec2 describe-instances \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[].Instances[].{InstanceId:InstanceId,State:State.Name,Type:InstanceType}' \
    --output table

echo "Existing infrastructure detected. No resources created."

echo "Validating experiment ownership tags..."

PROJECT_TAG_VALUE=$(aws ec2 describe-instances \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].Tags[?Key==`Project`].Value | [0]' \
    --output text)

EXPERIMENT_TAG_VALUE=$(aws ec2 describe-instances \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].Tags[?Key==`Experiment`].Value | [0]' \
    --output text)

if [[ "$PROJECT_TAG_VALUE" != "$PROJECT_TAG" ||
      "$EXPERIMENT_TAG_VALUE" != "$EXPERIMENT_ID" ]]; then
    echo "ERROR: Instance ownership tags do not match EXP-001." >&2
    exit 1
fi

echo "Ownership validated: ${PROJECT_TAG_VALUE} / ${EXPERIMENT_TAG_VALUE}"
