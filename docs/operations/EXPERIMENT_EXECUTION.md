# Execute EXP-001 and EXP-002 load campaigns

[← Deployment](INFRASTRUCTURE_DEPLOYMENT.md) · [Offline audit](OFFLINE_AUDIT.md) · [Results](../experiments/RESULTADOS_Y_ESTADISTICAS.md)

> **Historical closure does not require these commands.** `--execute` runs workloads against AWS resources and can incur charges. The original EC2 environment has been torn down; only use this chapter for an explicitly approved future campaign.

## Official test sequences

The currently documented source configuration is `experiments/exp001_capacity/config/test_sequence.yml` and `experiments/exp002_component_capacity/config/test_sequence.yml`. The historical design used two campaigns per experiment with five levels (10, 100, 200, 300, 500 users). **Check the actual YAML before asserting that the current sequence still matches those historical levels.**

## EXP-001

The audited `infrastructure_test/run.sh` reads `config/experiment.env` and requires `EVIDENCE_BUCKET` **before** processing `--dry-run`. Therefore, a dry run can fail without local configuration even when it does not create resources.

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
# Read the official YAML and environment requirements first; do not print secrets.
cat experiments/exp001_capacity/config/test_sequence.yml
# Requires a correctly configured local experiment.env even in the audited dry-run path:
bash experiments/exp001_capacity/infrastructure_test/run.sh --dry-run
# Only after deployment, verification and explicit approval:
bash experiments/exp001_capacity/infrastructure/bootstrap_all.sh run
```

The EXP-001 bootstrap `run` delegates to the official test runner; it is **not** a deployment command. Inspect its current `run.sh` for supported `--sequence-config` and evidence synchronization behavior before changing sequences.

## EXP-002

The audited EXP-002 runner supports `--dry-run` without loading the AWS environment; the `--execute` path does require active infrastructure and evidence configuration.

```bash
cat experiments/exp002_component_capacity/config/test_sequence.yml
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh run --dry-run
# Only after infrastructure verification, AWS permission and cost approval:
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh run --execute
```

The audited direct runner also supports `--sequence-config <path>` for alternative YAML; do not invent or restore removed historical sequence files without reviewing the current repository.

## Evidence checklist

| Stage | Expected evidence / check |
|---|---|
| PRE | Infrastructure inventory, service readiness, CloudWatch and Linux/SSM observations |
| RUN | RUN_ID, campaign, scenario, request count, throughput, p95, error rate, CPU/memory by instance and source |
| POST | Recovery observations, execution status, logs and evidence upload confirmation |
| Archive | S3 evidence path, locally retained reports, evidence hash, metadata and missing-data flags |
| Decision | Model proposal, effective policy decision, SLA state and rationale consistency |

Keep `execution_status` distinct from `sla_status`: the historical EXP-001 LB-04 case had a failed execution but `sla_status=PASS`. EXP-002 never had a formal SLA verdict (`NOT_EVALUATED`).

## Do not over-interpret short campaigns

The historical 60–120 second windows provide scenario snapshots, not seasonality, long-term reliability, steady-state CPU saturation or measured savings. More sustained testing and role-aware telemetry are future work.
