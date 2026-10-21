#!/usr/bin/env python3
"""Discover experiment EC2 instances using AWS resource tags."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def aws_json(arguments, profile, region):
    command = [
        "aws", *arguments,
        "--region", region,
        "--output", "json",
    ]

    if profile:
        command.extend(["--profile", profile])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("AWS CLI executable not found") from exc

    if result.returncode:
        raise RuntimeError(
            f"AWS CLI failed: {result.stderr.strip()}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AWS CLI returned invalid JSON") from exc


def discover_instances(args):
    filters = [
        {"Name": "tag:Project", "Values": [args.project]},
        {"Name": "tag:Experiment", "Values": [args.experiment]},
        {"Name": "tag:Environment", "Values": [args.environment]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ]

    response = aws_json(
        [
            "ec2", "describe-instances",
            "--filters", json.dumps(filters),
        ],
        args.profile,
        args.region,
    )

    instances = []

    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            tags = {
                tag["Key"]: tag["Value"]
                for tag in instance.get("Tags", [])
            }

            instances.append({
                "instance_id": instance["InstanceId"],
                "role": tags.get("Role"),
                "name": tags.get("Name"),
                "instance_type": instance.get("InstanceType"),
                "state": instance["State"]["Name"],
                "tags": tags,
            })

    instances.sort(key=lambda item: item["instance_id"])

    if not instances:
        raise RuntimeError(
            f"No running EC2 instances found for {args.experiment}"
        )

    return {
        "schema_version": "1.0",
        "source": "Amazon EC2 DescribeInstances",
        "project": args.project,
        "experiment_id": args.experiment,
        "environment": args.environment,
        "region": args.region,
        "discovered_at_utc": datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "instance_count": len(instances),
        "instances": instances,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Discover EC2 instances by experiment tags."
    )

    parser.add_argument("--project", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()

    inventory = discover_instances(args)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    args.output.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Experiment: {args.experiment}")
    print(f"Discovered instances: {inventory['instance_count']}")

    for instance in inventory["instances"]:
        print(
            f"  {instance['instance_id']} "
            f"[{instance['role']}] "
            f"{instance['instance_type']}"
        )

    print(f"Inventory saved: {args.output}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
