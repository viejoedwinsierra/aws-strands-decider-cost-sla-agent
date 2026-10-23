"""Correlate existing CloudWatch telemetry with EXP-001 scenario windows."""

import json
from datetime import datetime, timezone
from pathlib import Path


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scenario_window(campaign, run_id):
    timeline = load_json(campaign / "experiment_timeline.json")
    matches = [
        scenario for scenario in timeline["scenarios"]
        if scenario["run_id"] == run_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one timeline window for {run_id}")

    scenario = matches[0]
    return (
        parse_time(scenario["started_at_utc"]),
        parse_time(scenario["finished_at_utc"]),
    )


def cloudwatch_summary(campaign, start, end):
    result = {}

    for path in sorted((campaign / "cloudwatch").glob("*.json")):
        document = load_json(path)
        instance_id = document["instance_id"]
        result[instance_id] = {}

        for metric_name, statistics in document.get("metrics", {}).items():
            result[instance_id][metric_name] = {}

            for statistic, series in statistics.items():
                if not isinstance(series, dict):
                    continue

                samples = [
                    item["value"]
                    for item in series.get("datapoints", [])
                    if start <= parse_time(item["timestamp"]) <= end
                    and isinstance(item.get("value"), (int, float))
                ]

                result[instance_id][metric_name][statistic] = {
                    "sample_count": len(samples),
                    "mean": sum(samples) / len(samples) if samples else None,
                    "minimum": min(samples) if samples else None,
                    "maximum": max(samples) if samples else None,
                }

    return result


def summarize_run(campaign, run_id):
    start, end = scenario_window(campaign, run_id)

    return {
        "run_id": run_id,
        "window": {
            "started_at_utc": start.isoformat(),
            "finished_at_utc": end.isoformat(),
        },
        "cloudwatch": cloudwatch_summary(campaign, start, end),
        "linux": linux_summary(campaign, start, end),
    }


def linux_summary(campaign, start, end):
    """Derive CPU and memory utilization from existing Linux snapshots."""
    result = {}

    for path in sorted((campaign / "linux").glob("*.jsonl")):
        instance_id = path.stem
        samples = []

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            item = json.loads(line)
            timestamp = parse_time(item["timestamp_utc"])
            samples.append((timestamp, item))

        samples.sort(key=lambda item: item[0])

        cpu_values = []
        memory_values = []
        snapshot_count = 0

        previous = None

        for timestamp, item in samples:
            if start <= timestamp <= end:
                snapshot_count += 1

                memory = item.get("memory", {})
                total = memory.get("MemTotal_kb")
                available = memory.get("MemAvailable_kb")

                if (
                    isinstance(total, (int, float))
                    and isinstance(available, (int, float))
                    and total > 0
                    and 0 <= available <= total
                ):
                    memory_values.append(
                        100 * (1 - available / total)
                    )

                if previous is not None:
                    previous_cpu = previous[1].get("cpu", {})
                    current_cpu = item.get("cpu", {})

                    total_delta = (
                        current_cpu.get("cpu_total_jiffies", 0)
                        - previous_cpu.get("cpu_total_jiffies", 0)
                    )
                    idle_delta = (
                        current_cpu.get("cpu_idle_jiffies", 0)
                        - previous_cpu.get("cpu_idle_jiffies", 0)
                    )

                    if total_delta > 0 and 0 <= idle_delta <= total_delta:
                        cpu_values.append(
                            100 * (1 - idle_delta / total_delta)
                        )

            previous = (timestamp, item)

        result[instance_id] = {
            "source": "Linux SSM snapshots",
            "snapshot_count": snapshot_count,
            "cpu_utilization_percent": {
                "sample_count": len(cpu_values),
                "mean": sum(cpu_values) / len(cpu_values)
                if cpu_values else None,
                "maximum": max(cpu_values) if cpu_values else None,
                "derivation": "delta_cpu_jiffies",
            },
            "memory_utilization_percent": {
                "sample_count": len(memory_values),
                "mean": sum(memory_values) / len(memory_values)
                if memory_values else None,
                "maximum": max(memory_values) if memory_values else None,
                "derivation": "MemAvailable/MemTotal",
            },
        }

    return result
