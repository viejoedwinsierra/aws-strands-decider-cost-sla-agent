"""Build evidence-grounded Decider inputs from Delivery 1 telemetry contract."""
import json
from src.analysis.telemetry_contract import normalize_run

REQUIRED = ("cpu_utilization", "memory_utilization", "capacity_headroom", "infrastructure_cost")


def prepare_evidence(record, observations):
    """Return structured contract, conservative guardrail metrics, and readable model context.

    Never average measurements across different instances, sources, or phases.
    A metric is available to the guardrail only if a valid measured/derived
    value exists; conflicting sources remain individually visible to the model.
    """
    contract = normalize_run({**record, "observations": observations})
    valid = [m for m in contract["measurements"]
             if m["value"] is not None and m["sample_count"] != 0
             and m["quality"] in ("observed", "derived")]
    additional = {}
    for metric in REQUIRED:
        candidates = [m for m in valid if m["metric"] == metric]
        # Do not imply a single workload-wide utilization from multiple instances.
        # The guardrail only tests evidence presence, not capacity sufficiency.
        additional[metric] = candidates[0]["value"] if candidates else None
    return contract, additional


def format_context(contract, history):
    """Serialize actual measurements and only prior/current historical records."""
    metrics = [m for m in contract["measurements"] if m["value"] is not None]
    missing = sorted({m["metric"] for m in contract["measurements"]
                      if m["value"] is None and not any(
                          x["metric"] == m["metric"] and x["value"] is not None
                          for x in contract["measurements"])})
    return (
        "Measured/derived telemetry for current run (preserve source, instance, "
        "aggregation, unit, sample count, and time window): "
        + json.dumps({"window": contract["window"], "measurements": metrics,
                      "missing_metrics": missing}, sort_keys=True)
        + ". Historical scenarios available at this decision time: "
        + json.dumps(history, sort_keys=True)
        + ". Do not infer cost or capacity headroom from CPU alone. "
          "Historical context does not imply model retraining."
    )
