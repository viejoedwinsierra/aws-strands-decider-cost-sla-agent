#!/usr/bin/env python3
"""EXP-001 evidence manifest generation and integrity checks.

This module deliberately leaves AWS orchestration to archive_evidence.sh.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

def generate(directory, run_id, require_cloudwatch):
    directory = Path(directory)
    require_cloudwatch = require_cloudwatch == "1"

    expected = [
        "exp001_stats.csv",
        "exp001_stats_history.csv",
        "exp001_failures.csv",
        "exp001_exceptions.csv",
        "metrics_normalized.json",
        "sla_evaluation.json",
    ]

    # New runs include a reproducible execution manifest.
    if (directory / "run_manifest.json").is_file():
        expected.append("run_manifest.json")

    # Include the EC2 inventory when available.
    # Historical runs may not contain this artifact.
    inventory_path = directory / "ec2_inventory.json"
    if inventory_path.is_file():
        expected.append("ec2_inventory.json")

    # Include the experiment timeline.
    timeline_path = directory / "experiment_timeline.json"
    if timeline_path.is_file() or require_cloudwatch:
        expected.append("experiment_timeline.json")

    # Derive CloudWatch evidence from the frozen EC2 inventory.
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        instance_ids = [item["instance_id"] for item in inventory["instances"]]

        if require_cloudwatch and not instance_ids:
            raise SystemExit("ERROR: Empty EC2 inventory for CloudWatch")

        if len(instance_ids) != len(set(instance_ids)):
            raise SystemExit("ERROR: Duplicate EC2 instance IDs")

        for instance_id in instance_ids:
            name = f"cloudwatch/{instance_id}.json"
            if require_cloudwatch or (directory / name).is_file():
                expected.append(name)

    elif require_cloudwatch:
        raise SystemExit("ERROR: EC2 inventory required for CloudWatch")

    # Require SSM diagnostics for new runs; preserve historical compatibility.
    diagnostic_name = "diagnostics/ssm_locust_execution.json"
    require_ssm_diagnostic = (
        os.environ.get("REQUIRE_SSM_DIAGNOSTIC", "0") == "1"
    )

    if require_ssm_diagnostic or (directory / diagnostic_name).is_file():
        expected.append(diagnostic_name)

    files = {}
    missing = []

    for name in expected:
        path = directory / name
        if not path.is_file():
            missing.append(name)
            continue

        content = path.read_bytes()
        files[name] = {
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    if not files:
        raise SystemExit("ERROR: No evidence files available")

    archive_status = "COMPLETE" if not missing else "PARTIAL"

    manifest = {
        "schema_version": "1.0",
        "experiment_id": "EXP-001",
        "run_id": run_id,
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_status": archive_status,
        "missing_files": missing,
        "files": files,
    }

    (directory / "evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Manifest generated: {len(files)} files")


def verify_local(directory, remote_manifest_path):
    directory = Path(directory)
    remote_manifest = Path(remote_manifest_path).read_bytes()
    local_manifest = (directory / "evidence_manifest.json").read_bytes()

    if remote_manifest != local_manifest:
        raise SystemExit("ERROR: S3 manifest differs from local manifest")

    manifest = json.loads(remote_manifest)
    for name, metadata in manifest["files"].items():
        content = (directory / name).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != metadata["sha256"]:
            raise SystemExit(f"ERROR: SHA-256 mismatch: {name}")
        if len(content) != metadata["size_bytes"]:
            raise SystemExit(f"ERROR: Size mismatch: {name}")

    print("ARCHIVE_VERIFICATION_PASSED")
    print(f"Verified files: {len(manifest['files'])}")


def verify_remote(manifest_path, prefix, profile, region):
    with open(manifest_path, encoding="utf-8") as file:
        manifest = json.load(file)

    for name, metadata in manifest["files"].items():
        command = [
            "aws", "--profile", profile, "--region", region,
            "s3", "cp",
            prefix + "/" + name,
            "-",
            "--no-progress",
        ]
        result = subprocess.run(command, capture_output=True, check=True)
        actual = hashlib.sha256(result.stdout).hexdigest()
        if actual != metadata["sha256"]:
            raise SystemExit(f"ERROR: Remote SHA-256 mismatch: {name}")
        if len(result.stdout) != metadata["size_bytes"]:
            raise SystemExit(f"ERROR: Remote size mismatch: {name}")

    print(f"S3_REMOTE_INTEGRITY_PASSED: {len(manifest['files'])} files")


def check_completeness(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    status = manifest.get("archive_status")
    missing = manifest.get("missing_files", [])

    if status != "COMPLETE" or missing:
        print(
            f"ERROR: Incomplete evidence archive: "
            f"status={status}, missing={missing}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("EVIDENCE_COMPLETENESS_PASSED")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate_parser = commands.add_parser("generate")
    generate_parser.add_argument("directory")
    generate_parser.add_argument("run_id")
    generate_parser.add_argument("require_cloudwatch", choices=["0", "1"])
    local_parser = commands.add_parser("verify-local")
    local_parser.add_argument("directory")
    local_parser.add_argument("remote_manifest_path")
    remote_parser = commands.add_parser("verify-remote")
    remote_parser.add_argument("manifest_path")
    remote_parser.add_argument("prefix")
    remote_parser.add_argument("profile")
    remote_parser.add_argument("region")
    complete_parser = commands.add_parser("check-completeness")
    complete_parser.add_argument("manifest_path")
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.directory, args.run_id, args.require_cloudwatch)
    elif args.command == "verify-local":
        verify_local(args.directory, args.remote_manifest_path)
    elif args.command == "verify-remote":
        verify_remote(args.manifest_path, args.prefix, args.profile, args.region)
    else:
        check_completeness(args.manifest_path)


if __name__ == "__main__":
    main()
