# Figures, methods and provenance

| Figure | Meaning | Source |
|---|---|---|
| `architecture.svg` | Conceptual experiment/inference workflow | Project architecture; diagrammatic, not measured |
| `cost_baseline_concept.svg` | Baseline vs workload cost decomposition | **Conceptual only**, not an AWS bill or measurement |
| `latency_by_scenario.svg` | p95 by load scenario and campaign | `reports/comparison/comparison_by_run.csv` |
| `throughput_by_scenario.svg` | Throughput by scenario and campaign | Same CSV |
| `cpu_by_instance.svg` | RUN-phase CPU per anonymized instance | `telemetry_contract.measurements` in local-model JSON |
| `memory_by_instance.svg` | RUN-phase memory per anonymized instance | Same JSON; Linux SSM-derived |
| `telemetry_coverage.svg` | Observation counts by experiment | Same JSON, `telemetry_counts` |
| `model_agreement.svg` | Raw vs effective agreement | Paired comparison CSV |

Recreate the figures with `python3 docs/images/generate_charts.py` from the repository root. Requires `matplotlib`; do not install it just to read the already committed SVG files. No AWS account, model inference or network calls are needed. The charts are **descriptive**, not proof of cost savings or sustained saturation.
