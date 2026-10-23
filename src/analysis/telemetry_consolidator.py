"""Offline historical telemetry consolidation for InfraVita."""

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return result.astimezone(timezone.utc)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def interval(start, end):
    start, end = parse_time(start), parse_time(end)
    if end <= start:
        raise ValueError("Invalid telemetry interval")
    return start, end


def quality(count, duration_seconds, source):
    """Conservative availability classification, not a coverage guarantee."""
    if count == 0:
        return "INSUFFICIENT"
    if duration_seconds <= 0:
        return "UNKNOWN"
    if count == 1:
        return "PARTIAL"

    # A sample count alone cannot prove continuous coverage.
    return "PARTIAL"


def collect_campaign(campaign):
    campaign = Path(campaign)
    timeline = load_json(campaign / "experiment_timeline.json")
    phases = timeline["phases"]

    phase_results = {}
    for name in ("PRE", "RUN", "POST"):
        phase = phases.get(name)
        if not phase:
            phase_results[name] = {"quality": "UNKNOWN", "instances": {}}
            continue

        start, end = interval(phase["start_utc"], phase["end_utc"])
        duration = (end - start).total_seconds()
        instances = {}

        for path in sorted((campaign / "cloudwatch").glob("*.json")):
            document = load_json(path)
            instance_id = document["instance_id"]
            series = document.get("metrics", {}).get(
                "CPUUtilization", {}
            ).get("Average", {}).get("datapoints", [])

            timestamps = sorted({
                parse_time(point["timestamp"])
                for point in series
                if isinstance(point.get("value"), (int, float))
                and math.isfinite(point["value"])
                and start <= parse_time(point["timestamp"]) < end
            })

            instances.setdefault(instance_id, {})["cloudwatch"] = {
                "cpu_samples": len(timestamps),
                "timestamps": [t.isoformat() for t in timestamps],
                "quality": quality(len(timestamps), duration, "cloudwatch"),
            }

        for path in sorted((campaign / "linux").glob("*.jsonl")):
            instance_id = path.stem
            timestamps = []

            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                stamp = parse_time(item["timestamp_utc"])
                if start <= stamp < end:
                    timestamps.append(stamp)

            timestamps = sorted(set(timestamps))
            instances.setdefault(instance_id, {})["linux_ssm"] = {
                "snapshots": len(timestamps),
                "timestamps": [t.isoformat() for t in timestamps],
                "quality": quality(len(timestamps), duration, "linux_ssm"),
            }

        statuses = [
            source["quality"]
            for sources in instances.values()
            for source in sources.values()
        ]

        phase_results[name] = {
            "duration_seconds": duration,
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "instances": instances,
            "quality": (
                "UNKNOWN" if not statuses
                else "INSUFFICIENT" if all(
                    s == "INSUFFICIENT" for s in statuses
                )
                else "PARTIAL"
            ),
        }

    scenarios = []
    for item in timeline.get("scenarios", []):
        if not item.get("started_at_utc") or not item.get("finished_at_utc"):
            continue
        start, end = interval(
            item["started_at_utc"], item["finished_at_utc"]
        )
        scenarios.append({
            "scenario_id": item["scenario_id"],
            "run_id": item["run_id"],
            "started_at_utc": start.isoformat(),
            "finished_at_utc": end.isoformat(),
            "duration_seconds": (end - start).total_seconds(),
        })

    return {
        "campaign_id": timeline["campaign_id"],
        "phases": phase_results,
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
    }


def consolidate(root):
    root = Path(root)
    campaigns_root = root / "campaigns"

    campaigns = [
        collect_campaign(path)
        for path in sorted(campaigns_root.iterdir())
        if path.is_dir() and
        (path / "experiment_timeline.json").is_file()
    ] if campaigns_root.is_dir() else []

    campaigns.sort(
        key=lambda c: min(
            (parse_time(s["started_at_utc"]) for s in c["scenarios"]),
            default=datetime.max.replace(tzinfo=timezone.utc),
        )
    )

    total = sum(c["scenario_count"] for c in campaigns)
    return {
        "schema_version": "2.0",
        "source": "local_historical_evidence",
        "campaign_count": len(campaigns),
        "total_runs": total,
        "campaigns": campaigns,
        "limitations": [
            "Timestamp presence does not establish continuous coverage",
            "CloudWatch aggregation periods are not reconstructed",
            "Capacity headroom and actual billing costs are not inferred",
            "PRE and POST are campaign-level phases",
        ],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = consolidate(args.local_root)

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)

    print(json.dumps({
        "status": "SUCCESS",
        "campaign_count": report["campaign_count"],
        "total_runs": report["total_runs"],
        "phase_quality": {
            campaign["campaign_id"]: {
                name: phase["quality"]
                for name, phase in campaign["phases"].items()
            }
            for campaign in report["campaigns"]
        },
    }))


if __name__ == "__main__":
    main()
