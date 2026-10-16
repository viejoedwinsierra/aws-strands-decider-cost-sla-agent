# Benchmark V0.1 — AWS Cost & SLA Decision Agent

## 1. Objective

Evaluate the ability of Strands Decider 2B to select the
appropriate analytical tool from a technological system state
and an explicit decision question.

## 2. Available tools

- analyze_capacity
- evaluate_sla_risk
- estimate_cost_efficiency

## 3. Experimental design

Initial dataset: 30 scenarios.

- 10 capacity analysis scenarios
- 10 SLA risk scenarios
- 10 cost efficiency scenarios

Include:
- Clear scenarios
- Ambiguous scenarios
- Conflicting signals
- Different wording for similar decisions

## 4. Ground-truth labeling

The expected tool is determined by the analytical objective
and the available evidence, not by a single metric threshold.

Labels must be assigned before model execution.

## 5. Evaluation metrics

- Accuracy
- Macro-F1
- Confusion matrix
- Inference latency
- Model probabilities
- Reported confidence
- GPU memory utilization

## 6. Baseline

Compare Strands Decider 2B against a deterministic
rule-based tool selector.

## 7. Experimental controls

- Record model checkpoint and package version.
- Preserve original prompts and expected labels.
- Avoid modifying test labels after observing predictions.
- Separate model loading time from inference latency.
- Preserve raw results for reproducibility.

## 8. Scope

This benchmark evaluates tool selection.

It does not yet evaluate:
- Actual execution of analytical tools
- Infrastructure modifications
- Real AWS resource costs
- End-to-end SLA optimization

## 9. Current status

Local CUDA inference validated.

Three initial smoke tests completed successfully:
- Capacity: correct
- SLA Risk: correct
- Cost Efficiency: correct

These preliminary results are not part of the final
30-scenario evaluation dataset.
