#!/usr/bin/env python3
"""Verify installed distribution versions match an offline wheel lock."""
import importlib.metadata as md
import json
import re
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
lines = lock_path.read_text().splitlines()
if not lines or any(not re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+", line) for line in lines):
    raise SystemExit("Invalid or empty requirements.lock")
normalize = lambda name: re.sub(r"[-_.]+", "-", name).lower()
expected = {}
for line in lines:
    name, version = line.split("==", 1)
    key = normalize(name)
    if key in expected:
        raise SystemExit(f"Duplicate locked package: {key}")
    expected[key] = version
actual = {normalize(dist.metadata["Name"]): dist.version for dist in md.distributions()}
mismatches = {name: {"expected": version, "actual": actual.get(name)}
              for name, version in expected.items() if actual.get(name) != version}
if mismatches:
    print(json.dumps({"status": "FAIL", "mismatches": mismatches}, indent=2))
    raise SystemExit(1)
print(json.dumps({"status": "PASS", "locked_packages": len(expected)}, sort_keys=True))
