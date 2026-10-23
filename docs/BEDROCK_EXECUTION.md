# Amazon Bedrock execution and credential separation

The historical Bedrock provider was Amazon Nova Micro (`us.amazon.nova-micro-v1:0`) in `us-east-2`. Bedrock used a separate AWS account/API key from the AWS Academy infrastructure/S3 account.

## Secure credential setup

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
source /home/edwin/.venvs/infravita-decider/bin/activate
source scripts/load_bedrock_credentials.sh
```

The loader is intended to prompt for or securely load `AWS_BEARER_TOKEN_BEDROCK` in the current shell; do not echo the token, use `set -x`, write it into Markdown, or commit environment files. Confirm that the currently installed script still behaves as expected before sourcing it.

## Historical invocation

```bash
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp001_capacity/results \
  --provider bedrock --decision-policy computational-v1 \
  --output reports/bedrock/exp001_bedrock.json
```

Repeat with the EXP-002 root and output path when new inference is explicitly authorized. **`--offline` only controls the evidence source; Bedrock inference still uses a network API and may incur charges.** Do not overwrite published JSON evidence without retaining the prior snapshot.

## Verification without Bedrock charges

```bash
python3 docs/validation/validate_report_integrity.py
python3 -m json.tool reports/bedrock/exp001_bedrock.json >/dev/null
python3 -m json.tool reports/bedrock/exp002_bedrock.json >/dev/null
```

The documented Bedrock output is a historical artifact, not a promise of identical results from new generative requests. EXP-002's structured SLA remained `NOT_EVALUATED` and its effective recommendations were conservatively gated.
