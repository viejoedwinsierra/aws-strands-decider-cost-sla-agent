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


def evaluate(decision: dict, evidence: dict, policy="legacy") -> dict:
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

    if policy == "legacy":
        required = REQUIRED_METRICS
    elif policy == "computational-v1":
        required = ("cpu_utilization", "memory_utilization")
    else:
        raise ValueError(f"Unsupported guardrail policy: {policy}")
    missing = [metric for metric in required if additional_metrics.get(metric) is None]
    if policy == "computational-v1":
        efficiency = evidence.get("efficiency", {})
        sla_status = evidence.get("sla_status")
        if model_choice == "Optimize":
            if sla_status != "PASS":
                missing.append("sla_pass_required_for_optimize")
            if efficiency.get("cpu_vcpu_seconds_per_successful_request_estimated") is None:
                missing.append("cpu_efficiency")
            # No baseline/alternative capacity or credit behavior means a
            # resize recommendation is unsafe, even with low mean CPU.
            missing.append("validated_optimization_alternative")
        elif model_choice == "Scale Up":
            if sla_status not in ("FAIL", "FAILED", "BREACH"):
                missing.append("sla_degradation_for_scale_up")
            missing.append("validated_capacity_bottleneck")
        elif model_choice == "Maintain" and sla_status != "PASS":
            missing.append("sla_pass_required_for_maintain")
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
        "policy_version": "experimental-v0.2" if policy == "legacy" else "computational-v1",
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
