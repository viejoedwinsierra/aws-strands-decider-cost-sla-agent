# InfraVita V2 — Deployment, Experiments, and Model Inference Runbook

> Reproducibility guide for the Strands Decider 2B hackathon. Run commands from the repository root on WSL/Linux. The deployment and experiment commands below use the **existing project orchestrators**, not internal runners directly. Review costs and permissions before creating AWS resources.

## 1. Scope and architecture

- **EXP-001:** HTTP capacity and load testing.
- **EXP-002:** FastAPI + PostgreSQL component capacity testing.
- **Evidence:** AWS CloudWatch, SSM/Linux snapshots and Amazon S3, with historical local copies for model inference.
- **Decision engines:** Strands Decider 2B (local) and Amazon Bedrock (remote).
- **Policy:** `computational-v1`; decisions are advisory, not automated infrastructure changes.

`--offline` means **use local evidence / offline local-model dependencies**. It does **not** make Amazon Bedrock requests offline: `--provider bedrock` still calls the remote service and may incur charges.

## 2. Repository and existing Python environment

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1

# Reuse the already prepared environment; do not recreate it.
export INFRAVITA_PYTHON=/home/edwin/.venvs/infravita-exp002-v64/bin/python
"$INFRAVITA_PYTHON" --version

# Check project-managed dependencies, without installing anything.
bash scripts/start_agent.sh --check
```

The repository's `scripts/start_agent.sh` delegates dependency validation to `scripts/setup_agent.sh` and respects `INFRAVITA_PYTHON`. If the existing environment is different, set this variable to its actual Python executable.

### Optional dependency installation (only when the check fails)

```bash
# Review missing or incompatible packages first.
bash scripts/setup_agent.sh --check

# Explicit opt-in: install only missing/incompatible dependencies.
bash scripts/start_agent.sh --install-missing --check
```

Do **not** use `--install-all` unless a full dependency replacement is intentionally required. The setup script deliberately avoids installing/replacing PyTorch automatically. For a fully offline validation, use `bash scripts/start_agent.sh --check --offline`; installing missing packages in offline mode requires them to be available in a local package cache.

## 3. AWS profiles and security checks

Use the **AWS Academy** credentials for experimental infrastructure and S3. Bedrock uses **separate account credentials/API key**. Never paste credentials into terminal recordings, documentation, shell history, or Git.

```bash
aws configure list-profiles
aws sts get-caller-identity --profile academy-sandbox \
  --query '{Account:Account,Arn:Arn}' --output json
```

Check which profile the infrastructure orchestrator loads before deploying; do not assume that `--profile academy-sandbox` on the identity command changes the default profile for later commands.

## 4. EXP-001 — Deploy and run via the top-level orchestrator

The EXP-001 orchestrator `experiments/exp001_capacity/infrastructure/bootstrap_all.sh` loads experiment configuration before dispatching `deploy` or `run`. **Do not execute `infrastructure_test/run.sh` directly**: it may fail with `ENVIRONMENT: parameter null or not set` because its environment has not been initialized.

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1

# Step A — Deploy the experiment infrastructure (billable resources).
bash experiments/exp001_capacity/infrastructure/bootstrap_all.sh deploy

# Step B — Execute the experiment and collect evidence.
bash experiments/exp001_capacity/infrastructure/bootstrap_all.sh run
```

Confirm deployment and test success from the orchestrator output, RUN_ID, and evidence records. The `run` command is not a deployment command. Do not repeat `deploy` when resources are already active without checking for duplication.

## 5. EXP-002 — Verify its orchestrator before running

The repository snapshot includes `experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh`, but its exact CLI contract should be checked in the current checkout before execution:

```bash
sed -n '1,180p' experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh
```

If it exposes the same `deploy` and `run` subcommands, use that orchestrator rather than internal scripts:

```bash
# Run ONLY after verifying the supported subcommands and AWS context.
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh deploy
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh run
```

Deployment is optional when using existing historical evidence to demonstrate model inference.

## 6. Configure Amazon Bedrock API key securely

Do this **before screen recording**. Keep the Academy AWS profile separate from the independent Bedrock account. The credential-loader path below was used in the prior workflow; **verify that it exists in your current checkout** (it was not present in the repository snapshot inspected when preparing this guide).

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
export INFRAVITA_PYTHON=/home/edwin/.venvs/infravita-exp002-v64/bin/python

if [ -f scripts/load_bedrock_credentials.sh ]; then
  source scripts/load_bedrock_credentials.sh
else
  echo 'Credential loader not found: use the secure Bedrock setup documented for this checkout.'
fi

export INFRAVITA_BEDROCK_REGION=us-east-2
```

**Verify the actual Bedrock bridge configuration** before relying on `INFRAVITA_BEDROCK_REGION`: the variable name and supported region/model depend on the current bridge implementation. Never print the key or run `env` while recording. A remote Bedrock call can incur charges.

## 7. Run Amazon Bedrock inference — both experiments

These are the project invocation patterns used for the demonstration. They process locally available experiment results and write separate output reports.

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
export INFRAVITA_PYTHON=/home/edwin/.venvs/infravita-exp002-v64/bin/python
mkdir -p reports/bedrock

bash scripts/start_agent.sh \
  --offline --infer \
  --local-root experiments/exp001_capacity/results \
  --provider bedrock \
  --decision-policy computational-v1 \
  --output reports/bedrock/exp001_bedrock.json

bash scripts/start_agent.sh \
  --offline --infer \
  --local-root experiments/exp002_component_capacity/results \
  --provider bedrock \
  --decision-policy computational-v1 \
  --output reports/bedrock/exp002_bedrock.json
```

**Note:** Verify that each `--local-root` contains the expected evidence layout before running. `start_agent.sh` checks the existing Python environment on every invocation. The Bedrock request itself remains online despite `--offline`.

## 8. Run Strands Decider 2B locally — same evidence

Use the **same experiment evidence roots and decision policy** as Bedrock for a fair comparison. No Bedrock API key is required for local inference.

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
export INFRAVITA_PYTHON=/home/edwin/.venvs/infravita-exp002-v64/bin/python
mkdir -p reports/local

bash scripts/start_agent.sh \
  --offline --infer \
  --local-root experiments/exp001_capacity/results \
  --provider local \
  --decision-policy computational-v1 \
  --output reports/local/exp001_local.json

bash scripts/start_agent.sh \
  --offline --infer \
  --local-root experiments/exp002_component_capacity/results \
  --provider local \
  --decision-policy computational-v1 \
  --output reports/local/exp002_local.json
```

## 9. Validate output files and compare decisions

```bash
python3 - <<'PY'
import json
from pathlib import Path

paths = [
    Path('reports/bedrock/exp001_bedrock.json'),
    Path('reports/bedrock/exp002_bedrock.json'),
    Path('reports/local/exp001_local.json'),
    Path('reports/local/exp002_local.json'),
]
for path in paths:
    if not path.is_file():
        print(f'MISSING: {path}')
        continue
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        print(f'INVALID: {path}: {exc}')
        continue
    print(f'VALID JSON: {path} | top-level type: {type(data).__name__}')
PY
```

For meaningful comparison, align **experiment + RUN_ID + evidence version**, and distinguish:

1. Raw model recommendation (local versus Bedrock).
2. Policy/guardrail outcome (`computational-v1`).
3. Insufficient-evidence cases and SLA status.
4. Any differences in input coverage, inference time, and model version.

**Do not** treat agreement as accuracy, claim measured cost savings without a baseline, or present `NOT_EVALUATED` SLA as a pass. Historical analyses and newly generated experiments must remain separately identifiable.

## 10. Suggested hackathon recording sequence

1. **Infrastructure:** show `bootstrap_all.sh deploy` and successful resource creation (avoid revealing account secrets).
2. **Experiment:** show `bootstrap_all.sh run`, RUN_ID and evidence collection.
3. **Agent:** show local and Bedrock inference on the same evidence, JSON reports, and the final policy decision.

Edit the three clips into **one public demo shorter than three minutes**, showing a genuine Strands Decider 2B decision. The public video URL must be included in the AWS Builder Center submission.

## 11. Cleanup and repository hygiene

- Infrastructure deployments can incur AWS costs even when idle. Follow the **verified project cleanup procedure** after recording; do not guess a destructive command.
- Do not commit API keys, `.env` credentials, token files, raw secrets, or unreviewed runtime outputs.
- Check `git status` and `.gitignore` before committing reports.
- Keep this guide updated whenever the orchestrator interface or Bedrock authentication changes.

## 12. Known assumptions to verify in the current checkout

- `scripts/load_bedrock_credentials.sh` and its accepted API-key format.
- Region variable consumed by `src/decider/bedrock_bridge.py`.
- EXP-002 `bootstrap_all.sh` subcommand behavior.
- Evidence directories and whether the agent runner expects a parent folder or a particular RUN_ID layout.
- The official comparison-report command, if the current repository includes one.

This runbook intentionally does not invent missing scripts or claim that unverified commands were executed successfully.
