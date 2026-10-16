import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(
        description="Normalize Locust metrics for EXP-001"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--spawn-rate", type=float, default=1)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--target-ip", default=None)
    args = parser.parse_args()

    if not args.run_id or not all(
        c.isalnum() or c in "_-" for c in args.run_id
    ):
        parser.error("Invalid run-id")

    results = BASE / "results" / args.run_id
    source = results / "exp001_stats.csv"
    output = results / "metrics_normalized.json"

    with source.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    aggregated = next(
        (row for row in rows if row.get("Name") == "Aggregated"),
        None,
    )

    if aggregated is None:
        raise ValueError("Aggregated row not found in Locust CSV")

    requests = int(aggregated["Request Count"])
    failures = int(aggregated["Failure Count"])

    if requests <= 0:
        raise ValueError("No requests recorded; cannot evaluate SLA")

    metrics = {
        "schema_version": "1.0",
        "experiment_id": "EXP-001",
        "run_id": args.run_id,
        "source": {
            "tool": "Locust",
            "version": "2.46.7",
            "file": source.name,
            "record": "Aggregated",
        },
        "topology": {
            "load_generator": "EC2",
            "target": "EC2",
            "network": "AWS VPC private",
            "target_private_ip": args.target_ip,
            "target_port": 8080,
        },
        "configuration": {
            "users": args.users,
            "spawn_rate_users_per_second": args.spawn_rate,
            "configured_duration_seconds": args.duration,
        },
        "observations": {
            "request_count": requests,
            "failure_count": failures,
            "error_rate": failures / requests,
            "throughput_rps": float(aggregated["Requests/s"]),
            "latency_p50_ms": float(aggregated["50%"]),
            "latency_p95_ms": float(aggregated["95%"]),
            "latency_p99_ms": float(aggregated["99%"]),
            "latency_mean_ms": float(
                aggregated["Average Response Time"]
            ),
            "latency_max_ms": float(
                aggregated["Max Response Time"]
            ),
        },
        "data_quality": {
            "console_request_count": None,
            "csv_request_count": requests,
            "request_count_difference": None,
            "notes": (
                "Metrics obtained from Locust CSV. "
                "Console request count not independently verified."
            ),
        },
        "normalized_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    output.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"\nGenerated: {output}")


if __name__ == "__main__":
    main()
