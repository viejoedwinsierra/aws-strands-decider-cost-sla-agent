# Benchmark v0.2 — Intent-Guided Robustness Evaluation

## Objective
Evaluate Strands Decider 2B tool-selection robustness using 30 new scenarios.

## Dataset
- 10 scenarios per tool.
- 12 clear, 9 ambiguous, 9 conflicting scenarios.
- No reuse of benchmark v0.1 scenarios.
- Expected labels defined before inference.
- Labels must not be changed based on model predictions.

## Tool-selection policy
1. analyze_capacity: capacity, headroom, bottlenecks, resource constraints.
2. evaluate_sla_risk: SLA/SLO violations, reliability and service risk.
3. estimate_cost_efficiency: economic comparisons, total technological cost and trade-offs.

## Evaluation
- Accuracy and macro-F1.
- Per-tool precision and recall.
- Confusion matrix.
- Performance by difficulty.
- Inference latency and GPU memory.
- Comparison with a deterministic baseline.

## Limitations
This is an intent-guided evaluation, not autonomous decision-making.
Synthetic scenarios do not establish production performance.
The deterministic baseline must be defined before model results are inspected.
