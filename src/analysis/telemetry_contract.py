"""Evidence-first normalized telemetry contract (Delivery 1).

This module is read-only: it never fetches AWS metrics, fills missing values,
or mutates source evidence. Decision integration is deliberately a later phase.
"""

from __future__ import annotations

import math
from collections import Counter


METRIC_UNITS = {
    "cpu_utilization": "percent",
    "memory_utilization": "percent",
    "latency_p95": "ms",
    "throughput": "requests/second",
    "error_rate": "ratio",
    "request_count": "requests",
    "capacity_headroom": "percent",
    "infrastructure_cost": "USD",
}


def _measurement(metric, value, *, source, instance_id=None, aggregation="observed",
                 sample_count=None, quality="observed", phase="RUN"):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
        raise ValueError(f"Invalid measurement: {metric}={value!r}")
    if sample_count is not None and (not isinstance(sample_count, int) or sample_count < 0):
        raise ValueError("Invalid sample count")
    if value is None:
        quality = "missing"
    if quality not in {"observed", "derived", "estimated", "missing"}:
        raise ValueError("Unknown evidence quality")
    return {"metric": metric, "value": value, "unit": METRIC_UNITS[metric],
            "source": source, "instance_id": instance_id, "phase": phase,
            "aggregation": aggregation, "sample_count": sample_count, "quality": quality}


def normalize_run(record: dict) -> dict:
    """Produce measurements with provenance, retaining missing fields explicitly.

    Does not merge instance values: aggregating across roles without workload
    weights could hide saturation. CloudWatch statistics are kept separate.
    """
    telemetry = record["telemetry"]
    observations = record.get("observations", {})
    window = telemetry["window"]
    items = []
    for instance_id, metrics in sorted(telemetry.get("cloudwatch", {}).items()):
        for metric_name, statistics in sorted(metrics.items()):
            if metric_name.lower() != "cpuutilization":
                continue
            for statistic, summary in sorted(statistics.items()):
                count = summary.get("sample_count", 0)
                for aggregation in ("mean", "maximum", "minimum"):
                    value = summary.get(aggregation) if count else None
                    items.append(_measurement("cpu_utilization", value, source="cloudwatch",
                                              instance_id=instance_id,
                                              aggregation=f"{statistic}.{aggregation}",
                                              sample_count=count))
    for instance_id, metrics in sorted(telemetry.get("linux", {}).items()):
        for source_key, target_key in (("cpu_utilization_percent", "cpu_utilization"),
                                       ("memory_utilization_percent", "memory_utilization")):
            summary = metrics.get(source_key, {})
            count = summary.get("sample_count", 0)
            for aggregation in ("mean", "maximum"):
                items.append(_measurement(target_key, summary.get(aggregation) if count else None,
                                          source="linux_ssm", instance_id=instance_id,
                                          aggregation=aggregation, sample_count=count,
                                          quality="derived"))
    for source_key, metric in (("latency_p95_ms", "latency_p95"),
                               ("throughput_rps", "throughput"),
                               ("error_rate", "error_rate"),
                               ("request_count", "request_count")):
        items.append(_measurement(metric, observations.get(source_key),
                                  source="metrics_normalized", aggregation="run_summary"))
    for metric in ("capacity_headroom", "infrastructure_cost"):
        items.append(_measurement(metric, None, source="unavailable"))
    return {"schema_version": "1.0", "experiment_id": record["experiment_id"],
            "run_id": record["run_id"], "window": window, "measurements": items,
            "coverage": dict(Counter(item["quality"] for item in items))}


def main():
    """Audit existing historical evidence without model inference or AWS access."""
    import argparse
    import json
    from pathlib import Path
    from src.agent.official_integration import build_records, discover_runs

    parser = argparse.ArgumentParser()
    parser.add_argument("--local-root", default=".infravita/evidence/exp001")
    parser.add_argument("--output", default=".infravita/reports/telemetry_contract_v1.json")
    args = parser.parse_args()
    root = Path(args.local_root)
    runs = discover_runs(root)
    results = []
    for record in build_records(root):
        directory, files = runs[record["run_id"]]
        observations = json.loads(files[0].read_text(encoding="utf-8")).get("observations", {})
        normalized = normalize_run({**record, "observations": observations})
        results.append(normalized)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps({"schema_version": "1.0", "total_runs": len(results),
                                     "runs": results}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"TELEMETRY_CONTRACT_VALIDATED runs={len(results)} output={output}")


if __name__ == "__main__":
    main()
