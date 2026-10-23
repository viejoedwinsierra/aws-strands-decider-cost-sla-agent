# Operations guide — choose the correct mode

InfraVita has **three different operational workflows**, which must not be conflated:

| Workflow | AWS infrastructure required? | Invokes a model? | Documentation |
|---|---|---|---|
| Historical report audit | No | No | [Offline audit](OFFLINE_AUDIT.md) |
| Repeat local/Bedrock inference over cached evidence | No EC2; Bedrock requires network/API key | Yes | [Command reference](COMANDOS_PRINCIPALES.md) |
| Deploy and rerun experimental campaigns | Yes | Not inherently; inference is a separate step | [Infrastructure deployment](INFRASTRUCTURE_DEPLOYMENT.md), [Experiment execution](EXPERIMENT_EXECUTION.md) |

**Default for reviewing the published hackathon results:** offline audit. The historical infrastructure has already been removed. Deploy only with separate authorization and an explicit cost plan.

## Existing Python environment

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
source /home/edwin/.venvs/infravita-decider/bin/activate
bash scripts/start_agent.sh --check --offline
```

The `--check` flag does not run inference. Do not reinstall existing packages or replace the environment without evidence that it is broken.

## Reproducibility limits

Historical reports and RUN_ID hashes can be audited, but a new generative inference need not produce identical wording or decisions. A new AWS campaign creates new resource usage and evidence, not a replay of the 2026-10-23 measurements. Never report unmeasured costs as savings.
