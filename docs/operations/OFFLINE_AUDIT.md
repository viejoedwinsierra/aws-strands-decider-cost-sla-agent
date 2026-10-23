# Offline audit — no infrastructure, no inference

This workflow uses the **already committed** JSON reports. It makes no AWS API calls and does not invoke either model.

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
python3 docs/validation/compare_existing_reports.py
python3 -m json.tool reports/local_model/exp001_local.json >/dev/null
python3 -m json.tool reports/local_model/exp002_local.json >/dev/null
python3 -m json.tool reports/bedrock/exp001_bedrock.json >/dev/null
python3 -m json.tool reports/bedrock/exp002_bedrock.json >/dev/null
sha256sum reports/{local_model,bedrock}/*.json
```

The comparison script checks that the existing summary has 20 comparison rows; it is **not** a full cryptographic verification or an independent model-quality assessment. For a more comprehensive offline check, use the new [`validate_report_integrity.py`](../validation/validate_report_integrity.py), which checks pairings, SHA-256 equality across providers, report structure and expected counts. It does not validate AWS-origin authenticity or re-run the experiments.

```bash
python3 docs/validation/validate_report_integrity.py
```

For new inference (a **different workflow**), consult [Command reference](COMANDOS_PRINCIPALES.md). `--offline` only indicates local evidence input: using Bedrock still invokes a remote model and may cost money.
