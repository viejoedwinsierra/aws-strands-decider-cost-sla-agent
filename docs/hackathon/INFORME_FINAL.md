# InfraVita V2 — Experimental hackathon final report

**Evidence cut-off:** October 23, 2026
**Event:** Agent Experience Hackathon — Strands Decider 2B
**Status:** Experimental implementation and documentation published; external hackathon submission/acceptance not independently confirmed.

## Executive conclusion

InfraVita V2 is a **working decision-support prototype in evolution**, not a final product or an autonomous cloud cost optimizer. Its strongest demonstrated outcome is the controlled separation of **measured telemetry**, **model proposals** and **effective policy-governed recommendations** across two AWS experiments and two inference providers.

## Experimental coverage

- EXP-001: EC2 HTTP service and Locust; two campaigns, five load scenarios each.
- EXP-002: EC2 FastAPI and PostgreSQL; two campaigns, five scenarios each.
- Historical evidence: 20 unique RUN_IDs, 730 CloudWatch observations and 60 Linux SSM snapshots.
- Inference: 20 local Strands Decider 2B v21 and 20 Bedrock Nova Micro executions; all 40 reported as complete.
- Comparison: raw agreement 8/10 for EXP-001 and 5/10 for EXP-002; effective agreement 10/10 for EXP-002 due to conservative SLA guardrails.

![Latency and load](../images/latency_by_scenario.svg)

## Operational and economic insight

**A minimally deployed, connected, observable service can incur operating costs while idle.** This motivates separating a measurable `C_baseline` from load-dependent and support/change costs. The historical reports do not contain usable `infrastructure_cost` values; therefore the actual idle baseline, marginal cost per request, AWS spend and monetary savings **remain unmeasured**.

## Results and caveats

| Finding | Interpretation |
|---|---|
| EXP-001 SLA state: 10 `PASS` | One run separately has `execution_status=FAILED`; do not merge these fields |
| EXP-002 SLA state: 10 `NOT_EVALUATED` | No formal SLA PASS/FAIL conclusion is supported |
| EXP-002 p95 rises from ~10 to 1,400–1,500 ms | Suggests substantial latency degradation at higher load; not proof of an SLA violation without thresholds |
| EXP-002 effective decisions: all `Insufficient Evidence` | Deterministic guardrail blocked unsupported action |
| `capacity_headroom` and monetary cost unavailable | No verified rightsizing opportunity or savings claim |
| Short campaigns, limited CloudWatch samples | Not enough for seasonal demand or long-term reliability claims |

Some generated Bedrock explanations may assert an SLA pass inconsistent with structured `NOT_EVALUATED`; the structured fields and guardrail are authoritative. Confidence values are not comparable across models without calibration.

## Deliverables and reproducibility

[Documentation hub](../README.md) · [Deployment](../operations/INFRASTRUCTURE_DEPLOYMENT.md) · [Run tests](../operations/EXPERIMENT_EXECUTION.md) · [Offline validation](../operations/OFFLINE_AUDIT.md) · [Results](../experiments/RESULTADOS_Y_ESTADISTICAS.md) · [Model comparison](../models/COMPARACION_LOCAL_BEDROCK.md).

The four committed JSON reports and `comparison_by_run.csv` preserve run-level results. The infrastructure has been removed, so historical review is **offline-first**. Recreating EC2 resources or calling Bedrock again is neither necessary nor implied by this report.

## Next milestones — not achieved in the current MVP

1. Measure the minimum idle infrastructure cost using inventory, billing and controlled uptime windows.
2. Run longer CPU/memory/queue saturation and recovery campaigns with role attribution.
3. Define formal SLA thresholds for EXP-002 and validate service-level outcomes.
4. Estimate marginal cost per request and compare optimization alternatives with actual charges.
5. Validate model rationale consistency, uncertainty and policy correctness independently.
6. Extend to multi-service lifecycle decisions: maintain, optimize, scale, modernize and retire.

**Final assessment:** The prototype provides a reproducible foundation for evidence-based infrastructure decisions. It does not yet demonstrate a production-grade optimizer, autonomous changes or verified cost savings.
