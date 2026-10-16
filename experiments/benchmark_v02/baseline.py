import re
from collections import Counter

TOOLS = (
    "analyze_capacity",
    "evaluate_sla_risk",
    "estimate_cost_efficiency",
)

KEYWORDS = {
    "analyze_capacity": (
        "capacity", "headroom", "bottleneck", "throughput",
        "bandwidth", "workload", "resource constraint",
        "processing volume", "replicas", "saturated",
        "connection pool", "arrival rate",
    ),
    "evaluate_sla_risk": (
        "sla", "slo", "service commitment", "availability",
        "reliability", "breach", "violation", "error budget",
        "failure rate", "recovery objective",
        "contractual", "service-level",
    ),
    "estimate_cost_efficiency": (
        "cost", "spending", "saving", "economically",
        "economic", "price", "monthly", "hourly",
        "charges", "penalties", "financial",
        "cost per", "fee", "bill",
    ),
}


def predict(state, question):
    """Deterministic keyword baseline; no ground-truth access."""
    scores = Counter()

    # Prioritize the requested decision over incidental telemetry.
    for tool, keywords in KEYWORDS.items():
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"

            if re.search(pattern, question, re.IGNORECASE):
                scores[tool] += 3

            if re.search(pattern, state, re.IGNORECASE):
                scores[tool] += 1

    # Fixed tie-breaking order, independent of ground-truth labels.
    return max(TOOLS, key=lambda tool: scores[tool])


if __name__ == "__main__":
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parent
    scenarios = json.loads(
        (base / "scenarios.json").read_text(encoding="utf-8")
    )

    results = []

    for scenario in scenarios:
        selected = predict(scenario["state"], scenario["question"])
        results.append({
            "scenario_id": scenario["scenario_id"],
            "expected_tool": scenario["expected_tool"],
            "selected_tool": selected,
            "correct": selected == scenario["expected_tool"],
        })

    accuracy = sum(r["correct"] for r in results) / len(results)

    print(f"Baseline scenarios: {len(results)}")
    print(f"Baseline accuracy: {accuracy:.4f}")
    print("Predictions:", dict(Counter(r["selected_tool"] for r in results)))
