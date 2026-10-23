# InfraVita V2 integration patch

This archive is an **overlay**: extract into the repository root, do not delete existing files. It retains existing `src/decider` implementations. It does not modify experiment runners, and it does not include `experiments/exp001_capacity/config/test_sequence.yml` or the user's untracked `evidence_sources.yaml`.

## Install separately (once)

```bash
bash scripts/setup_agent.sh
# Optional heavy model packages only when needed:
# INSTALL_DECIDER=1 bash scripts/setup_agent.sh
```

## Run local analysis without installing or accessing AWS

```bash
bash scripts/analyze.sh --local-root experiments/exp001_capacity/results
```

The local analysis requires each run directory to contain `metrics_normalized.json`, `sla_evaluation.json`, and `evidence_manifest.json`. The report is written to `.infravita/reports/latest.json`. `checkpoint.json` prevents reprocessing unchanged run inputs. `--watch` enables repeated polling.

## Sync and watch S3

```bash
export EVIDENCE_BUCKET=<your-evidence-bucket>
export AWS_PROFILE=academy-sandbox
bash scripts/start_agent.sh --config experiments/exp001_capacity/config/evidence_sources.yaml
```

The existing `evidence_sources.yaml` remains untouched. Use `config/evidence_sources.example.yaml` as a template only if it is absent. Sync uses AWS CLI; the profile must already be configured. It does not install packages, provision EC2, or run Locust.

## Model integration status

The source bundle does not contain an executable Strands Decider 2B model invocation or a confirmed runtime API. The runner therefore defaults to deterministic historical summaries and explicitly labels `decider_status: DISABLED`. A **verified** external model executable can be connected with `--decider-command <executable> [args...]`, receiving a JSON state on stdin and returning the actual model output on stdout in the shape required by `src/decider/decision_guardrail.py`. This is an integration interface, **not** a claim of successful model inference. Do not use a fabricated or hard-coded decision as a substitute.

## Limitations before production

- Evidence manifest existence is checked, but manifest integrity/completeness is **not yet verified** by this V2 prototype. Do not treat this as certified evidence integrity. Existing EXP-001 archiver performs separate verification.
- EXP-002's legacy analysis scripts contain EXP-001 S3 prefixes. This patch deliberately does not change experiment scripts.
- Output is local JSON. S3 publishing and the model runtime are not included yet.
- One agent process per workspace; no multi-process checkpoint locking.
- Source paths must point at results prefixes and have valid AWS permissions.
- When a model command is enabled, failures are surfaced as PARTIAL and checkpoints are not advanced.

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q src
bash -n scripts/*.sh
```
