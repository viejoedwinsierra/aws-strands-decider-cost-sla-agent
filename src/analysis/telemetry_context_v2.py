"""Compact, conservative historical telemetry context."""

import json
from collections import defaultdict
from datetime import timedelta

from src.analysis.telemetry_consolidator import parse_time
from src.analysis.telemetry_history import historical_measurements


def build_historical_context(root, as_of, *, cloudwatch_lag_seconds=120):
    cutoff = parse_time(as_of)

    if cloudwatch_lag_seconds < 0:
        raise ValueError("CloudWatch lag cannot be negative")

    cloudwatch_cutoff = cutoff - timedelta(
        seconds=cloudwatch_lag_seconds
    )

    measurements = historical_measurements(
        root,
        mode="decision_time",
        as_of=cutoff.isoformat(),
    )

    groups = defaultdict(list)
    linux_snapshots = defaultdict(int)

    for item in measurements:
        timestamp = parse_time(item["timestamp_utc"])

        if item["source"] == "cloudwatch":
            if timestamp > cloudwatch_cutoff:
                continue

            # CPU Average only; other metrics remain in raw evidence.
            if (item["metric"] != "CPUUtilization"
                    or item["statistic"] != "Average"):
                continue

            key = (
                item["campaign_id"],
                item["instance_id"],
                "cloudwatch_cpu",
            )
            groups[key].append(item["value"])

        elif item["source"] == "linux_ssm":
            key = (item["campaign_id"], item["instance_id"])
            linux_snapshots[key] += 1

    summary = []

    for key, values in sorted(groups.items()):
        campaign_id, instance_id, metric = key
        summary.append({
            "campaign_id": campaign_id,
            "instance_id": instance_id,
            "metric": metric,
            "sample_count": len(values),
            "mean": sum(values) / len(values),
            "maximum": max(values),
            "quality": "PARTIAL",
        })

    for key, count in sorted(linux_snapshots.items()):
        campaign_id, instance_id = key
        summary.append({
            "campaign_id": campaign_id,
            "instance_id": instance_id,
            "metric": "linux_snapshot_count",
            "sample_count": count,
            "quality": "PARTIAL",
        })

    return {
        "as_of": cutoff.isoformat(),
        "cloudwatch_lag_seconds": cloudwatch_lag_seconds,
        "telemetry_quality": "PARTIAL" if summary else "UNKNOWN",
        "measurements": summary,
        "limitations": [
            "Historical summaries do not prove continuous coverage",
            "CloudWatch lag is a conservative heuristic, not publication evidence",
            "Linux snapshot counts do not represent CPU utilization",
            "Infrastructure cost and headroom are not inferred",
        ],
    }


def format_historical_context(root, as_of):
    context = build_historical_context(root, as_of)
    return (
        ". Historical telemetry context (timestamp-filtered, "
        "quality not validated): "
        + json.dumps(context, sort_keys=True)
    )
