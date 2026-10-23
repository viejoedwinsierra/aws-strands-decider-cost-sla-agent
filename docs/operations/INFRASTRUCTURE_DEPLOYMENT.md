# Infrastructure deployment — AWS-active procedure

[← Documentation hub](../README.md) · [Run campaigns](EXPERIMENT_EXECUTION.md) · [Offline-only audit](OFFLINE_AUDIT.md)

> **Safety boundary:** This chapter documents how the existing official scripts are intended to be used. It does **not** mean resources are currently deployed. The original infrastructure was removed. Deploying EC2, networking, storage or monitoring can generate charges even before any load test begins. Obtain budget/authorization first.

## Prerequisites and account separation

- Run from the repository root in WSL Ubuntu; reuse the existing Python environment. Do not install anything unless a preflight reports a missing dependency.
- Use the **AWS Academy** sandbox/profile only for experiment infrastructure and S3 evidence, when authorized. Bedrock credentials belong to a **separate account** and must not be used for infrastructure deployment.
- Verify the active account and region without printing credentials: `aws sts get-caller-identity --profile academy-sandbox` and `aws configure get region --profile academy-sandbox`. Profile names and permissions must match the current environment; the academy sandbox may have expired or changed.
- Check EC2 quota, SSM connectivity, security groups, tags, S3 bucket discovery and a budget. Evidence storage is mandatory in the experiment design. The exact current configuration must be checked locally; **do not hardcode a bucket name**.
- Do not enable inbound SSH/PostgreSQL ports for convenience; preserve the project's SSM-first security model.

## EXP-001 — HTTP service and Locust

The audited official bootstrap supports explicit `deploy` and `run` modes. **Do not invoke it without a subcommand**: the audited version defaults to `run`.

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
source /home/edwin/.venvs/infravita-decider/bin/activate
bash scripts/start_agent.sh --check --offline
# Only after AWS account, configuration, permissions and cost approval:
bash experiments/exp001_capacity/infrastructure/bootstrap_all.sh deploy
bash experiments/exp001_capacity/infrastructure/verify.sh
```

Expected system: HTTP EC2, Locust EC2, SSM management, CloudWatch/Linux SSM evidence, S3 evidence destination. Actual instances, IDs, regions and availability depend on the current deployment.

## EXP-002 — FastAPI and PostgreSQL

The audited official bootstrap supports `deploy`, `resume`, `verify`, `run`.

```bash
# Only after AWS authorization and configuration review:
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh deploy
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh verify
```

`resume` is an existing mode, **not** a guarantee of idempotency. Review the current script and state before using it. EXP-002 includes an API and PostgreSQL EC2 component; inspect the active deployment inventory before attributing any cost to a particular instance.

## Before and after deploying

1. Record timestamp, AWS account ID (in private operational records), region, EC2 instance types and states, EBS volumes, public IPv4, network components, S3 storage, CloudWatch settings and resource tags.
2. Capture an **idle-but-running baseline** with no load: wall-clock time, resource inventory, CPU/memory and actual billing/cost data when available. Distinguish AWS billable usage from monitoring snapshots.
3. Run only the officially configured experiments after validating the sequence; see [Experiment execution](EXPERIMENT_EXECUTION.md).
4. Archive evidence to S3 and local historical packages. Confirm completeness and hash lineage.
5. Decommission resources only under explicit authorization and after preserving evidence; this package intentionally does not guess a teardown command.

## Cost accounting boundaries

A running EC2 instance may accrue compute cost even at low utilization. Attached EBS storage, public IPv4 and monitoring/logging can add charges. Networking charges depend on actual configuration and traffic; do not assume every network component incurs a fixed hourly charge. No price, USD baseline or realized savings was measured in the historical reports. See the [cost hypothesis](../../README.md#the-core-economic-question-what-does-the-minimum-running-service-cost).
