# InfraVita V2 - Amazon Bedrock Execution

## Objective

Run the InfraVita Cost & SLA Decision Agent against historical
EXP-001 and EXP-002 evidence using Amazon Bedrock.

Compare Bedrock decisions with the local Strands Decider 2B v21 model.

## AWS account separation

AWS Academy is used for experimental infrastructure and S3 evidence.

The independent AWS account is used for Amazon Bedrock inference.

Do not use the academy-sandbox profile for Bedrock.

## Authentication

Run this command from the repository root:

    source scripts/load_bedrock_credentials.sh

The script prompts for the API key without displaying it.

The API key is stored in the current shell environment only.

Never store credentials in Git, experiment.env, or report files.

## Execute EXP-001

    mkdir -p reports/bedrock

    bash scripts/start_agent.sh --offline --infer \
      --local-root experiments/exp001_capacity/results \
      --provider bedrock \
      --decision-policy computational-v1 \
      --output reports/bedrock/exp001_bedrock.json

## Execute EXP-002

    bash scripts/start_agent.sh --offline --infer \
      --local-root experiments/exp002_component_capacity/results \
      --provider bedrock \
      --decision-policy computational-v1 \
      --output reports/bedrock/exp002_bedrock.json

## Expected reports

- reports/local_model/exp001_local.json
- reports/local_model/exp002_local.json
- reports/bedrock/exp001_bedrock.json
- reports/bedrock/exp002_bedrock.json

## Execution status

Local inference completed successfully for both experiments.

Bedrock execution has been attempted, but the bridge returned exit code 1.
The underlying error has not yet been identified.

No successful Bedrock inference has been confirmed.

## Completion criteria

Both Bedrock reports must be generated, with ten decisions per experiment.

The final analysis must compare local and Bedrock decisions,
confidence values, guardrails, SLA risks and cost optimization.

The results must be documented without inventing metrics.
