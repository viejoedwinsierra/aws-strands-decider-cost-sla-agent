# Delivery 9 - Architecture Baseline

## Evidence-to-decision flow

1. Historical campaign and run artifacts are discovered from an explicit local evidence root.
2. Normalized run evidence is validated for required files and unique RUN_ID.
3. EXP-specific telemetry summarization produces CloudWatch and Linux evidence.
4. Telemetry is normalized into the shared decision contract.
5. Computational resource consumption and efficiency features are calculated where available.
6. evidence_adapter.build_state builds the model request.
7. One inference provider is selected: local Strands Decider 2B or Amazon Bedrock Nova Micro.
8. decision_guardrail.evaluate produces the effective decision and guardrail reasons.
9. official_integration.py writes a JSON report with evidence hashes, telemetry counts, model result, and guarded result.

## Separation of responsibilities

- Strands Decider 2B local: local decision model.
- Amazon Nova Micro: independent Bedrock-hosted inference provider.
- Decision guardrail: deterministic evidence-policy layer; not a model.
- EXP-001 / EXP-002: evidence-producing experiments with distinct telemetry adapters.
- Official integration: historical evidence processing primitive, not yet the Delivery 9 campaign orchestrator.

## Delivery 9 architectural constraint

The dual runner should orchestrate existing integration logic instead of cloning telemetry, evidence adaptation, model bridge, or guardrail logic. Dataset identity must be explicit so incomplete campaigns cannot contaminate a comparison cycle.
