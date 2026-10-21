#!/usr/bin/env python3
import json
import sys
from pathlib import Path

inventory = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
instances = inventory["instances"]

for role in ("http-server", "load-generator"):
    matches = [item["instance_id"] for item in instances if item.get("role") == role]
    if len(matches) != 1:
        raise SystemExit(
            f"ERROR: Expected exactly one EC2 with Role={role}; found {len(matches)}"
        )
    print(matches[0])
