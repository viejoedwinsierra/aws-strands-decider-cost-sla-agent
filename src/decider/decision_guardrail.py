#!/usr/bin/env python3
"""Evidence-based decision guardrail for EXP-001."""

import argparse
import json
from pathlib import Path

OPTIONS = {
    "Maintain",
    "Optimize",
    "Scale Up",
    "Insufficient Evidence",
}

REQUIRED_METRICS = (
    "cpu_utilization",
    "memory_utilization",
    "capacity_headroom",
    "infrastructure_cost",
)


def evaluate(decision: dict, evidence: dict) -> dict:
    answer = decision["answers"]["choice_0"]
    model_choice = answer["choice"]

    if model_choice not in OPTIONS:
        raise ValueError(f"Unsupported decision: {model_choice}")

    probability = answer["probabilities"][model_choice]
    confidence = answer["confidence"]

    if not 0 <= probability <= 1:
        raise ValueError("Invalid model probability")

    if not 0 <= confidence <= 1:
        raise ValueError("Invalid model confidence")

    additional_metrics = evidence.get("additional_metrics", {})

    missing = [
        metric
        for metric in REQUIRED_METRICS
        if additional_metrics.get(metric) is None
    ]

    guardrail_applied = bool(missing)

    effective_choice = (
        "Insufficient Evidence"
        if guardrail_applied
        else model_choice
    )

    return {
        "experiment_id": evidence["experiment_id"],
        "run_id": evidence["run_id"],
        "model_decision": model_choice,
        "model_probability": probability,
        "model_confidence": confidence,
        "effective_decision": effective_choice,
        "guardrail_applied": guardrail_applied,
        "decision_overridden": effective_choice != model_choice,
        "missing_evidence": missing,
        "policy_version": "experimental-v0.2",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decision_file", type=Path)
    parser.add_argument("evidence_file", type=Path)
    args = parser.parse_args()

    decision = json.loads(
        args.decision_file.read_text(encoding="utf-8")
    )
    evidence = json.loads(
        args.evidence_file.read_text(encoding="utf-8")
    )

    print(json.dumps(evaluate(decision, evidence), indent=2))


if __name__ == "__main__":
    main()
