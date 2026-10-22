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
    parser.add_argument("--users", type=int, default=None)
    parser.add_argument("--spawn-rate", type=float, default=None)
    parser.add_argument("--duration", type=int, default=None)
    parser.add_argument("--target-ip", default=None)
    args = parser.parse_args()

    if not args.run_id or not all(
        c.isalnum() or c in "_-" for c in args.run_id
    ):
        parser.error("Invalid run-id")

    results = BASE / "results" / args.run_id
    manifest_path = results / "run_manifest.json"
    if not manifest_path.is_file():
        parser.error(f"Required run manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != args.run_id or manifest.get("experiment_id") != "EXP-001":
        parser.error("Manifest run_id/experiment_id mismatch")
    config = manifest.get("configuration", {})
    try:
        users = int(config["users"])
        spawn_rate = float(config["spawn_rate_users_per_second"])
        duration = int(config["configured_duration_seconds"])
        target_ip = manifest["infrastructure"]["target_private_ip"]
    except (KeyError, ValueError, TypeError) as exc:
        parser.error(f"Invalid manifest configuration: {exc}")
    if users <= 0 or spawn_rate <= 0 or duration <= 0:
        parser.error("Manifest requires positive users, spawn_rate and duration")
    if args.users is not None and args.users != users:
        parser.error("--users disagrees with run_manifest.json")
    if args.spawn_rate is not None and abs(args.spawn_rate - spawn_rate) > 1e-9:
        parser.error("--spawn-rate disagrees with run_manifest.json")
    if args.duration is not None and args.duration != duration:
        parser.error("--duration disagrees with run_manifest.json")
    if args.target_ip is not None and args.target_ip != target_ip:
        parser.error("--target-ip disagrees with run_manifest.json")

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
            "target_private_ip": target_ip,
            "target_port": 8080,
        },
        "configuration": {
            "users": users,
            "spawn_rate_users_per_second": spawn_rate,
            "configured_duration_seconds": duration,
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
