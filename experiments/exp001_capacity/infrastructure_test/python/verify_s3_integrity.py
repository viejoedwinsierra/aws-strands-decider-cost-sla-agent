#!/usr/bin/env python3
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

local_path = Path(sys.argv[1])
s3_uri = sys.argv[2]
profile = sys.argv[3]
region = sys.argv[4]

with tempfile.TemporaryDirectory() as directory:
    remote_path = Path(directory) / "ec2_inventory.json"

    subprocess.run(
        [
            "aws", "s3", "cp",
            s3_uri, str(remote_path),
            "--profile", profile,
            "--region", region,
            "--no-progress",
        ],
        check=True,
    )

    local_hash = hashlib.sha256(local_path.read_bytes()).hexdigest()
    remote_hash = hashlib.sha256(remote_path.read_bytes()).hexdigest()

    if local_hash != remote_hash:
        raise SystemExit("ERROR: S3 inventory SHA-256 mismatch")

    print(f"EXP-001 | Inventory SHA-256: {local_hash}")
    print("EXP-001 | S3 inventory integrity verified")
