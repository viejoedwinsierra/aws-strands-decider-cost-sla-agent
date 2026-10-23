# Validation and security controls

## Safe, offline checks

```bash
bash scripts/start_agent.sh --check --offline
python3 docs/validation/validate_report_integrity.py
python3 docs/validation/compare_existing_reports.py
git diff --check
```

## AWS-active checks (only with authorization)

- Verify AWS account and role before deployment; never mix Academy infrastructure credentials with the separate Bedrock account.
- Confirm resource tags, SSM access, security groups, S3 evidence configuration and operational budget.
- Use the official deployment/verification scripts and inspect `test_sequence.yml` before campaigns.
- Archive PRE/RUN/POST evidence, hash it and review missing telemetry before inference.
- Remove experimental infrastructure only after explicit approval and evidence preservation.

## Publication controls

Never commit real API keys, AWS tokens, private keys, unredacted logs or credentials inside ZIP archives. A regular-expression scan can flag suspicious literals but cannot prove absence of secrets. Published `project.env` must be checked manually for private values. The historical reports contain instance identifiers and timestamps; review their disclosure policy before making a repository public.
