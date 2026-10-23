# Traceability and validation without inference

| Operation | Runs a model? | Needs AWS? |
|---|---|---|
| `bash scripts/start_agent.sh --check --offline` | No | No |
| `bash scripts/setup_agent.sh --check --offline` | No | No |
| `python3 docs/validation/validate_report_integrity.py` | No | No |
| `python3 docs/validation/compare_existing_reports.py` | No | No |
| `bash scripts/start_agent.sh --offline --infer --provider local ...` | Yes, local | No EC2 required |
| `bash scripts/start_agent.sh --offline --infer --provider bedrock ...` | Yes, remote | Bedrock account/API required |

`--local-root` selects historical evidence; `--output` writes JSON; `--decision-policy computational-v1` applies deterministic safety checks. `--capacity-inventory` is an optional integration argument when supported by the installed version. `--install-missing` and `--install-all` can install packages and are **not** read-only checks.

## Reproducible audit

```bash
python3 docs/validation/validate_report_integrity.py
python3 docs/validation/compare_existing_reports.py
```

The audit verifies internal consistency of already generated reports and source pairing; it does not establish AWS provenance independently, re-run experiments, or prove recommendation accuracy. Record `experiment_id`, `run_id`, `evidence_sha256`, model/backend, raw decision, effective decision, override reason, SLA status, and missing measurements for every claim.
