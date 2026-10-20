#!/usr/bin/env python3
"""Persist SSM output and report concise Locust deployment status.

This helper is independent of the Bash deployment orchestration.
Usage: python3 report_locust_ssm.py invocation.json deployment.log
"""
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: report_locust_ssm.py RESULT_JSON RESULT_LOG", file=sys.stderr)
        return 2
    source, destination = map(Path, sys.argv[1:])
    try:
        result = json.loads(source.read_text(encoding="utf-8"))
        stdout = result.get("StandardOutputContent") or ""
        stderr = result.get("StandardErrorContent") or ""
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "=== SSM STDOUT ===\n" + stdout +
            "\n=== SSM STDERR ===\n" + stderr + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"[ERROR] Unable to process SSM result: {exc}", file=sys.stderr)
        return 2
    status = result.get("Status", "Unknown")
    print(f"[INFO] SSM status: {status}")
    print(f"[INFO] Detailed log: {destination}")
    print(f"[INFO] Raw result: {source}")
    if status != "Success":
        print("[ERROR] Locust deployment failed; inspect detailed log.", file=sys.stderr)
        return 1
    print("[OK] Locust deployment completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
