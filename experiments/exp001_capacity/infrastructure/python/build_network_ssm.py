#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/verify_network.sh."""
import json
import sys
from pathlib import Path

destination = Path(sys.argv[1])
ip = sys.argv[2]

commands = [
    "set -eu",
    f"curl --fail --silent --show-error --connect-timeout 5 --max-time 15 "
    f"http://{ip}:8080/health",
    "echo",
    "echo NETWORK_VERIFICATION_PASSED",
]

destination.write_text(json.dumps({"commands": commands}))
