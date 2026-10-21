#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

duration = os.environ["DURATION"]
if not duration.endswith("s") or not duration[:-1].isdigit():
    raise SystemExit("ERROR: DURATION must use seconds, e.g. 60s")

manifest = {
    "schema_version": "1.0",
    "experiment_id": "EXP-001",
    "run_id": os.environ["RUN_ID"],
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
    "aws_region": os.environ["AWS_REGION"],
    "infrastructure": {
        "http_instance_id": os.environ["HTTP_INSTANCE_ID"],
        "locust_instance_id": os.environ["LOCUST_INSTANCE_ID"],
        "target_private_ip": os.environ["HTTP_IP"],
        "target_port": 8080,
    },
    "configuration": {
        "users": int(os.environ["USERS"]),
        "spawn_rate_users_per_second": float(os.environ["SPAWN_RATE"]),
        "configured_duration_seconds": int(duration[:-1]),
    },
    "source_commit": os.environ["SOURCE_COMMIT"] or None,
    "load_generator": {
        "tool": "Locust",
        "version": "2.46.7",
    },
}

Path(sys.argv[1]).write_text(
    json.dumps(manifest, indent=2) + "\n",
    encoding="utf-8",
)
