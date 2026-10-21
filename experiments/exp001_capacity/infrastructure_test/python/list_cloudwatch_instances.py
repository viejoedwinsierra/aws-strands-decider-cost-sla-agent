#!/usr/bin/env python3
import json
import sys
from pathlib import Path

inventory = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
instance_ids = [item["instance_id"] for item in inventory["instances"]]

if not instance_ids:
    raise SystemExit("ERROR: No EC2 instances available for CloudWatch")

if len(instance_ids) != len(set(instance_ids)):
    raise SystemExit("ERROR: Duplicate EC2 instance IDs in inventory")

for instance_id in instance_ids:
    print(instance_id)
