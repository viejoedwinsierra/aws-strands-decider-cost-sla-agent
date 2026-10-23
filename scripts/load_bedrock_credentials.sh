#!/usr/bin/env bash

# InfraVita V2 - Amazon Bedrock API key loader
# Usage: source scripts/load_bedrock_credentials.sh

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "ERROR: Execute using: source scripts/load_bedrock_credentials.sh"
    exit 1
fi

if [[ "${AWS_PROFILE:-}" == "academy-sandbox" ]]; then
    echo "ERROR: AWS Academy profile cannot be used for Bedrock."
    return 1
fi

if [[ ! -t 0 ]]; then
    echo "ERROR: An interactive terminal is required."
    return 1
fi

read -r -s -p "Amazon Bedrock API key: " BEDROCK_KEY
echo

if [[ -z "$BEDROCK_KEY" ]]; then
    echo "ERROR: API key cannot be empty."
    unset BEDROCK_KEY
    return 1
fi

export AWS_BEARER_TOKEN_BEDROCK="$BEDROCK_KEY"
unset BEDROCK_KEY

export INFRAVITA_BEDROCK_REGION="${INFRAVITA_BEDROCK_REGION:-us-east-2}"

# Prevent use of another AWS profile.
unset AWS_PROFILE

echo "BEDROCK_CREDENTIALS_LOADED"
echo "Region: $INFRAVITA_BEDROCK_REGION"
echo "API key: configured (hidden)"
