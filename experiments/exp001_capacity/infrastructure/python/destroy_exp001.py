#!/usr/bin/env python3
"""Validate ownership and terminate only the two configured EXP-001 EC2 instances."""
import argparse
import json
import os
import re
import subprocess
import sys


def aws(*args):
    command = ["aws", "--profile", os.environ["AWS_PROFILE"], "--region", os.environ["AWS_REGION"], *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"AWS CLI failed: {' '.join(args[:2])}: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if os.environ.get("EXPERIMENT_ID") != "EXP-001":
        raise ValueError("Only EXP-001 is supported")
    project = os.environ["PROJECT_TAG"]
    targets = {
        "http-server": os.environ["HTTP_INSTANCE_ID"],
        "load-generator": os.environ["LOCUST_INSTANCE_ID"],
    }
    if len(set(targets.values())) != 2:
        raise ValueError("HTTP and Locust instance IDs must differ")
    if not all(re.fullmatch(r"i-[0-9a-f]{8,17}", instance) for instance in targets.values()):
        raise ValueError("Invalid instance ID in experiment.env")

    account = aws("sts", "get-caller-identity")["Account"]
    response = aws("ec2", "describe-instances", "--instance-ids", *targets.values())
    instances = [i for reservation in response.get("Reservations", []) for i in reservation.get("Instances", [])]
    found = {i["InstanceId"]: i for i in instances}
    print(f"Account: {account} | Region: {os.environ['AWS_REGION']} | Profile: {os.environ['AWS_PROFILE']}")
    print(f"Project: {project} | Experiment: EXP-001")
    for role, instance_id in targets.items():
        instance = found.get(instance_id)
        if instance is None:
            raise ValueError(f"Instance not found: {instance_id}")
        tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
        expected = {"Project": project, "Experiment": "EXP-001", "Role": role}
        if any(tags.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Ownership mismatch for {instance_id}: expected {expected}, got {tags}")
        state = instance["State"]["Name"]
        print(f"Verified: {role}: {instance_id} | state={state}")
    active = [i for i in targets.values() if found[i]["State"]["Name"] != "terminated"]
    if args.dry_run:
        print("DRY RUN: no AWS resources changed. To terminate use: bash infrastructure/destroy.sh --execute")
        return
    if not active:
        print("All configured instances are already terminated.")
        return
    print("Terminating configured EC2 instances...")
    aws("ec2", "terminate-instances", "--instance-ids", *active)
    command = ["aws", "--profile", os.environ["AWS_PROFILE"], "--region", os.environ["AWS_REGION"],
               "ec2", "wait", "instance-terminated", "--instance-ids", *active]
    subprocess.run(command, check=True)
    print("SUCCESS: all targeted EC2 instances terminated. S3 and shared network resources retained.")
    print("NOTE: experiment.env still contains the old IDs; do not reuse them for a new deployment.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
