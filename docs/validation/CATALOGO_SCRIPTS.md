# Official scripts and validation catalogue

Script names and mode claims were checked against the supplied audited repository snapshot. **The current WSL repository may have evolved since that snapshot.** Review `--help` or source before any AWS-active action.

| Entry point | Verified role | Operational caution |
|---|---|---|
| `experiments/exp001_capacity/infrastructure/bootstrap_all.sh` | `deploy`, `run` | Defaults to `run` if omitted; always pass a mode |
| `experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh` | `deploy`, `resume`, `verify`, `run` | Requires AWS for active modes; `run --dry-run` supported |
| `experiments/exp001_capacity/infrastructure_test/run.sh` | Experiment sequence, `--dry-run`, `--sequence-config` | Reads `experiment.env` before dry-run in audited version |
| `experiments/exp002_component_capacity/infrastructure_test/run.sh` | `--dry-run`, `--execute`, `--sequence-config` | `--execute` runs load and writes evidence |
| `experiments/*/infrastructure/verify.sh` | Deployed resource checks | Needs AWS resources |
| `scripts/start_agent.sh` | `--check`, `--offline`, `--infer`, install flags | `--offline --provider bedrock` still makes network calls |
| `scripts/setup_agent.sh` | Dependency preflight / optional installation | Prefer `--check`; no installation without approval |
| `scripts/load_bedrock_credentials.sh` | Secure token setup | Never print token or use `set -x` |
| `src/agent/official_integration.py` | Historical evidence and inference integration | Use official entry point |
| `src/decider/decision_guardrail.py` | Computational decision policy | Preserve raw and effective recommendations |
| `docs/validation/compare_existing_reports.py` | Lightweight existing report comparison | Checks row count; not full hash verification |
| `docs/validation/validate_report_integrity.py` | Offline structural/pairing audit | No AWS, no model; not external provenance proof |

[Deployment procedure](../operations/INFRASTRUCTURE_DEPLOYMENT.md) · [Experiment execution](../operations/EXPERIMENT_EXECUTION.md) · [Offline audit](../operations/OFFLINE_AUDIT.md)
