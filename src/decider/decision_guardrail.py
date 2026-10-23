#!/usr/bin/env python3
"""Evidence-based decision guardrail for EXP-001."""

import argparse
import json
import hashlib
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


def validate_optimization_alternative(evidence):
    """Require an independently measured feasible alternative, not a model claim."""
    alt = evidence.get("optimization_alternative") or {}
    return (alt.get("validated") is True
            and isinstance(alt.get("expected_savings_fraction"), (int, float))
            and 0 < alt["expected_savings_fraction"] <= 1
            and alt.get("sla_preserved") is True
            and alt.get("telemetry_quality") == "VALID")


def validate_capacity_bottleneck(evidence):
    """High mean CPU alone cannot establish server saturation."""
    bottleneck = evidence.get("capacity_bottleneck") or {}
    signals = bottleneck.get("signals") or {}
    return (bottleneck.get("validated") is True
            and bottleneck.get("component") == "http_server"
            and bottleneck.get("telemetry_quality") == "VALID"
            and signals.get("throughput_plateau") is True
            and signals.get("latency_or_errors_degraded") is True
            and signals.get("locust_generator_healthy") is True
            and signals.get("resource_constraint") is True)


def evaluate(decision: dict, evidence: dict, policy="legacy") -> dict:
    answer = decision["answers"]["choice_0"]
    model_choice = answer["choice"]

    if model_choice not in OPTIONS:
        raise ValueError(f"Unsupported decision: {model_choice}")

    probability = answer["probabilities"][model_choice]
    confidence = answer["confidence"]

    is_bedrock = decision.get("provider") == "amazon-bedrock"

    if is_bedrock:
        if probability is not None or confidence is not None:
            raise ValueError("Uncalibrated Bedrock confidence must be null")
    else:
        if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
            raise ValueError("Invalid model probability")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
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
            if not validate_optimization_alternative(evidence):
                missing.append("validated_optimization_alternative")
        elif model_choice == "Scale Up":
            if sla_status not in ("FAIL", "FAILED", "BREACH"):
                missing.append("sla_degradation_for_scale_up")
            if not validate_capacity_bottleneck(evidence):
                missing.append("validated_capacity_bottleneck")
        elif model_choice == "Maintain" and sla_status != "PASS":
            missing.append("sla_pass_required_for_maintain")
    guardrail_applied = bool(missing)

    effective_choice = (
        "Insufficient Evidence"
        if guardrail_applied
        else model_choice
    )

    evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "evidence_sha256": evidence_hash,
        "input_state": {"sla_status": evidence.get("sla_status"), "telemetry_quality": evidence.get("telemetry_quality", "UNKNOWN")},
        "guardrail_reasons": missing,
        "experiment_id": evidence["experiment_id"],
        "run_id": evidence["run_id"],
        "model_decision": model_choice,
        "model_probability": probability,
        "model_confidence": confidence,
        "confidence_calibrated": not is_bedrock,
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
