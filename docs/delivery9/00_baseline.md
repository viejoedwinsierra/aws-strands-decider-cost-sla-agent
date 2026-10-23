# Delivery 9 - Phase 1 Baseline Audit

- Audit timestamp (UTC): 2026-10-23T19:18:33Z
- Source: user-provided repository ZIP
- Declared reference commit: 1ba455e - feat(decider): integrate Amazon Bedrock inference for EXP-001 and EXP-002
- Commit verification: not possible from this ZIP because it contains no .git directory
- Audit mode: offline/read-only for source and evidence; documentation files added only after validation

## Scope

This baseline covers only issues affecting reproducibility, correctness, comparability, traceability, security, or final presentation. No infrastructure was deployed, no load test was repeated, no evidence was modified, and no model inference was invoked during this phase.

## Repository state observed

The ZIP contains 439 files before these Delivery 9 documentation additions. Expected high-level components are present: src/agent, src/decider, src/analysis, src/evidence, EXP-001, EXP-002, shared experiment tooling, tests, configuration, and documentation directories.

Core integration files found:

- src/agent/official_integration.py
- src/agent/runner.py
- src/decider/local_bridge.py
- src/decider/bedrock_bridge.py
- src/decider/decision_guardrail.py
- src/decider/evidence_adapter.py

The root README is still primarily organized around EXP-001 and is not yet the final dual-experiment hackathon guide.

## Verified architecture behavior

### Official historical integration

src/agent/official_integration.py discovers campaign summaries and normalized run evidence, requires both CloudWatch and Linux telemetry, computes evidence hashes, adapts EXP-001/EXP-002 telemetry, builds decision state, invokes either the local bridge or the Bedrock bridge, and applies the deterministic guardrail.

The CLI currently supports one evidence root and one provider per invocation. It does not yet implement the requested multi-experiment/multi-provider/cycle/resume execution contract for Delivery 9.

### Local model bridge

src/decider/local_bridge.py is offline-oriented, reuses a local checkpoint, resolves the strands-decider executable from the active Python environment by default, disables Hugging Face network access, and executes the model through the CLI. It currently defaults to CUDA.

### Bedrock bridge

src/decider/bedrock_bridge.py targets us.amazon.nova-micro-v1:0 in us-east-2 by default, requires AWS_BEARER_TOKEN_BEDROCK, uses temperature 0, validates the returned option, and deliberately emits null probability/confidence values.

### Guardrail

src/decider/decision_guardrail.py preserves the model decision separately from the effective decision. Under computational-v1 it requires CPU and memory evidence and adds decision-specific conditions for Optimize, Scale Up, and Maintain. Unsupported or insufficient evidence is converted to Insufficient Evidence rather than relaxing policy requirements.

## Baseline validation results

### Automated tests

Command: python3 -m pytest -q

Observed result:

- 63 passed
- 5 skipped
- 1 failed

Failure: tests/test_telemetry_consolidator.py::TelemetryConsolidatorTests::test_real_historical_evidence_when_available expects 14 EXP-001 runs across two campaigns, but only 9 materialized valid runs are present in the supplied ZIP.

### EXP-001 official integration without inference

Command used against the evidence physically present in the ZIP:

python3 -m src.agent.official_integration --local-root experiments/exp001_capacity/results --output /tmp/exp001_official_noinfer.json --decision-policy computational-v1

Observed result: SUCCESS, 9 records processed without inference.

The first EXP-001 campaign materializes LB-01 through LB-05 and records LB-06/LB-07 as not evaluated. The second materializes LB-01 through LB-04 and records LB-05/LB-06/LB-07 as not evaluated. Therefore the supplied experiments/exp001_capacity/results tree represents 9 processable records, not the separate confirmed 7-record historical inference set described for Delivery 9.

### EXP-002 official integration without inference

Command:

python3 -m src.agent.official_integration --local-root experiments/exp002_component_capacity/results --output /tmp/exp002_official_noinfer.json --decision-policy computational-v1

Observed result: FAILED before inference.

Reason: campaign exp002_campaign_20261023T145906Z references run exp002_campaign_20261023T145906Z_DB-SMOKE, but that run has no corresponding normalized evidence directory in the ZIP. A later completed campaign contains DB-01, DB-02, and DB-03 with normalized evidence.

## Reconciliation with previously confirmed historical results

Delivery 9 states that the validated historical inference roots are:

- .infravita/evidence/exp001 - 7 records
- .infravita/evidence/exp002-validation-copy - 3 records

Those hidden runtime evidence roots are not included in the supplied ZIP. Consequently, this ZIP can validate source structure and the included experiment result trees, but it cannot independently reproduce the exact previously confirmed 7 + 3 inference baseline without restoring or reconstructing those historical evidence roots in a controlled way.

This is a reproducibility gap, not evidence that the previously confirmed model runs were invalid.

## Prioritized findings

### P0 - Canonical historical evidence roots absent

The exact 7-record EXP-001 and 3-record EXP-002 roots used for the validated local/Bedrock runs are absent from the ZIP. Delivery 9 must define a canonical, non-destructive method to locate or reconstruct the intended datasets before the dual runner is considered reproducible.

### P0 - EXP-002 mixes incomplete and completed campaigns

The official integration aborts when pointed at the supplied EXP-002 results root because it encounters an incomplete DB-SMOKE campaign whose normalized run evidence is absent. The final runner must either select an explicit campaign/dataset or apply a documented eligibility rule; it must not silently fabricate evidence.

### P1 - EXP-001 test drift

The telemetry consolidator test expects 14 runs, but the supplied result tree has 9 materialized processable runs. Campaign safety-gate semantics must be reconciled before changing code or tests.

### P1 - Delivery 9 runner contract not implemented

The official integration accepts one root, one provider, and one output per execution. It does not yet provide experiment selection, provider matrix execution, cycles, Bedrock call caps, resumability, per-record error isolation, or consolidated comparison.

### P1 - Automatic model comparison not present

No dedicated RUN_ID-level local-vs-Bedrock comparator/report was found in the ZIP.

### P2 - Final documentation incomplete

The root README does not yet document the complete EXP-001 + EXP-002 + local model + Bedrock + comparison + guardrail closure flow. docs/hackathon is effectively empty in this ZIP.

### P2 - Release hygiene

The ZIP contains Python bytecode/cache files, temporary pre-delivery source backups, runtime logs, and a pyproject backup even though .gitignore excludes many of these classes. This does not prove they are tracked in Git because .git is absent, but they should not be included in a clean final release unless intentionally retained outside version control.

### P2 - Secret scan baseline

A pattern scan found no assignments for AWS access keys, AWS secret keys, AWS_BEARER_TOKEN_BEDROCK, or private-key headers in the ZIP. This is only a baseline pattern scan and does not replace the final staged-file secret review.

## Phase 1 exit decision

Phase 1 source/architecture audit is complete, but the project cannot be declared reproducible yet. Phase 2 should preserve official_integration.py as the processing primitive and add a bounded orchestration layer, explicit dataset selection/reconciliation, and a RUN_ID comparator. No guardrail relaxation is justified by the current findings.
