# Command reference — verified entry points

[Deployment](INFRASTRUCTURE_DEPLOYMENT.md) · [Run campaigns](EXPERIMENT_EXECUTION.md) · [Offline audit](OFFLINE_AUDIT.md)

## Safe preflight (no AWS deployment, no model inference)

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
source /home/edwin/.venvs/infravita-decider/bin/activate
bash scripts/start_agent.sh --check --offline
python3 docs/validation/validate_report_integrity.py
```

## AWS infrastructure (authorization required)

```bash
bash experiments/exp001_capacity/infrastructure/bootstrap_all.sh deploy
bash experiments/exp001_capacity/infrastructure/verify.sh
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh deploy
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh verify
```

## Load tests (authorization required)

```bash
# EXP-001: config/experiment.env is required even for dry-run in the audited snapshot
bash experiments/exp001_capacity/infrastructure_test/run.sh --dry-run
bash experiments/exp001_capacity/infrastructure/bootstrap_all.sh run
# EXP-002: dry-run avoids AWS environment loading in the audited snapshot
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh run --dry-run
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh run --execute
```

## Local inference over historical evidence (invokes local model)

```bash
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp001_capacity/results \
  --provider local --decision-policy computational-v1 \
  --output reports/local_model/exp001_local.json
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp002_component_capacity/results \
  --provider local --decision-policy computational-v1 \
  --output reports/local_model/exp002_local.json
```

## Bedrock inference over historical evidence (remote AWS model; possible cost)

```bash
source scripts/load_bedrock_credentials.sh
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp001_capacity/results \
  --provider bedrock --decision-policy computational-v1 \
  --output reports/bedrock/exp001_bedrock.json
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp002_component_capacity/results \
  --provider bedrock --decision-policy computational-v1 \
  --output reports/bedrock/exp002_bedrock.json
```

**Never print or commit credentials.** The Bedrock API key comes from a separate AWS account, not the Academy infrastructure profile. Re-running these commands overwrites report paths; back up published evidence first.
