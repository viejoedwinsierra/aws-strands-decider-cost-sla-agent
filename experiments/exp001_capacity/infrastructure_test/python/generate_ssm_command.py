#!/usr/bin/env python3
import json
import shlex
import sys
from pathlib import Path

output, ip, users, spawn_rate, duration, run_id, s3_prefix = sys.argv[1:]

remote_dir = f"/opt/exp001-locust/results/{run_id}"
csv_prefix = f"{remote_dir}/exp001"

command = " ".join(map(shlex.quote, [
    "/opt/exp001-locust/venv311/bin/locust",
    "-f", "/opt/exp001-locust/locustfile.py",
    "--headless",
    "--host", f"http://{ip}:8080",
    "--users", users,
    "--spawn-rate", spawn_rate,
    "--run-time", duration,
    "--csv", csv_prefix,
    "--exit-code-on-error", "1",
]))

commands = [
    "set -eu",
    f"mkdir -p {shlex.quote(remote_dir)}",
    "set +e",
    command,
    "LOCUST_EXIT_CODE=$?",
    "set -e",
    f"aws s3 sync {shlex.quote(remote_dir + '/')} {shlex.quote(s3_prefix + '/')} --sse AES256",
    'echo "LOCUST_EXIT_CODE=$LOCUST_EXIT_CODE"',
    'exit "$LOCUST_EXIT_CODE"',
]

Path(output).write_text(json.dumps({"commands": commands}))
