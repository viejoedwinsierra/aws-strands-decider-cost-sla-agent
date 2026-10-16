#!/usr/bin/env python3
"""Build a Decider state from EXP-001 evidence."""

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def build_state(run_directory: Path) -> dict:
    metrics = load_json(run_directory / "metrics_normalized.json")
    sla = load_json(run_directory / "sla_evaluation.json")

    for field in ("experiment_id", "run_id"):
        if metrics.get(field) != sla.get(field):
            raise ValueError(f"Evidence mismatch: {field}")

    observations = metrics["observations"]
    policy = sla["policy"]

    state = (
        f"Experiment: {metrics['experiment_id']}. "
        f"Run: {metrics['run_id']}. "
        f"HTTP requests: {observations['request_count']}. "
        f"Latency p95: {observations['latency_p95_ms']} ms "
        f"(maximum {policy['max_latency_p95_ms']} ms). "
        f"Error rate: {observations['error_rate'] * 100:.2f}% "
        f"(maximum {policy['max_error_rate'] * 100:.2f}%). "
        f"Throughput: {observations['throughput_rps']:.4f} requests/second "
        f"(minimum {policy['min_throughput_rps']} requests/second). "
        f"Experimental SLA status: {sla['overall_status']}. "
        "CPU utilization, memory utilization, capacity headroom, "
        "and infrastructure costs are not available in this evidence."
    )

    return {
        "experiment_id": metrics["experiment_id"],
        "run_id": metrics["run_id"],
        "state": state,
        "question": (
            "What is the most justified operational recommendation?"
        ),
        "options": [
            "Maintain",
            "Optimize",
            "Scale Up",
            "Insufficient Evidence",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()

    print(json.dumps(build_state(args.run_directory), indent=2))


if __name__ == "__main__":
    main()
