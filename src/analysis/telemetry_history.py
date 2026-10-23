"""Temporal views over InfraVita consolidated telemetry."""

from datetime import datetime, timezone
from src.analysis.telemetry_consolidator import parse_time


def _scenario_start(scenario):
    return parse_time(scenario["started_at_utc"])


def _scenario_end(scenario):
    return parse_time(scenario["finished_at_utc"])


def historical_view(report, *, mode, as_of=None):
    """Return scenario metadata available at a given decision time.

    This is a temporal index, not a complete metric-level evidence filter.
    """
    if mode not in ("decision_time", "retrospective"):
        raise ValueError("Unsupported historical mode")

    if mode == "decision_time" and as_of is None:
        raise ValueError("decision_time requires as_of")

    cutoff = parse_time(as_of) if as_of is not None else None
    scenarios = []

    for campaign in report["campaigns"]:
        for scenario in campaign["scenarios"]:
            if cutoff is not None and _scenario_end(scenario) > cutoff:
                continue

            scenarios.append({
                "campaign_id": campaign["campaign_id"],
                **scenario,
            })

    scenarios.sort(
        key=lambda item: (
            _scenario_end(item),
            _scenario_start(item),
            item["campaign_id"],
            item["run_id"],
        )
    )

    return {
        "mode": mode,
        "as_of": cutoff.isoformat() if cutoff else None,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "telemetry_quality": "UNKNOWN",
        "limitations": [
            "Temporal index contains scenario metadata only",
            "Campaign-level telemetry is not included",
            "Metric-level historical filtering is not implemented",
        ],
    }


def historical_measurements(root, *, mode, as_of=None):
    """Read raw timestamped telemetry without future leakage.

    Timestamp filtering is not equivalent to proof of metric availability
    at decision time, especially for CloudWatch aggregate datapoints.
    """
    import json
    import math
    from pathlib import Path

    if mode not in ("decision_time", "retrospective"):
        raise ValueError("Unsupported historical mode")
    if mode == "decision_time" and as_of is None:
        raise ValueError("decision_time requires as_of")

    cutoff = parse_time(as_of) if as_of else None
    result = []

    campaigns_root = Path(root) / "campaigns"
    if not campaigns_root.is_dir():
        return result

    for campaign in sorted(campaigns_root.iterdir()):
        timeline_path = campaign / "experiment_timeline.json"
        if not timeline_path.is_file():
            continue

        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        campaign_id = timeline["campaign_id"]

        for path in sorted((campaign / "cloudwatch").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            instance_id = document["instance_id"]

            for metric, statistics in document.get("metrics", {}).items():
                for statistic, series in statistics.items():
                    if not isinstance(series, dict):
                        continue

                    for point in series.get("datapoints", []):
                        value = point.get("value")
                        if (not isinstance(value, (int, float))
                                or not math.isfinite(value)):
                            continue

                        stamp = parse_time(point["timestamp"])
                        if cutoff is not None and stamp > cutoff:
                            continue

                        result.append({
                            "campaign_id": campaign_id,
                            "instance_id": instance_id,
                            "source": "cloudwatch",
                            "metric": metric,
                            "statistic": statistic,
                            "timestamp_utc": stamp.isoformat(),
                            "value": value,
                        })

        for path in sorted((campaign / "linux").glob("*.jsonl")):
            instance_id = path.stem

            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue

                point = json.loads(line)
                stamp = parse_time(point["timestamp_utc"])

                if cutoff is not None and stamp > cutoff:
                    continue

                result.append({
                    "campaign_id": campaign_id,
                    "instance_id": instance_id,
                    "source": "linux_ssm",
                    "timestamp_utc": stamp.isoformat(),
                    "cpu": point.get("cpu"),
                    "memory": point.get("memory"),
                })

    result.sort(
        key=lambda item: (
            item["timestamp_utc"],
            item["campaign_id"],
            item["instance_id"],
            item["source"],
            item.get("metric", ""),
            item.get("statistic", ""),
        )
    )

    return result
