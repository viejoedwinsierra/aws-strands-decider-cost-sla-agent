#!/usr/bin/env python3
"""Validate an EXP-001 SSM command invocation diagnostic."""

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = ("Status", "ResponseCode", "Output", "Errors")

TERMINAL_STATES = {
    "Success",
    "Failed",
    "Cancelled",
    "TimedOut",
    "Cancelling",
}


def validate_structure(data):
    if not isinstance(data, dict):
        raise ValueError("Diagnostic must be a JSON object")

    missing = [name for name in REQUIRED_FIELDS if name not in data]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

    if not isinstance(data["Status"], str):
        raise ValueError("Status must be a string")

    if (
        not isinstance(data["ResponseCode"], int)
        or isinstance(data["ResponseCode"], bool)
    ):
        raise ValueError("ResponseCode must be an integer")

    for name in ("Output", "Errors"):
        if not isinstance(data[name], str):
            raise ValueError(f"{name} must be a string")

    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("diagnostic", type=Path)
    parser.add_argument(
        "--mode",
        choices=("structure", "execution"),
        default="structure",
    )
    args = parser.parse_args()

    try:
        data = json.loads(args.diagnostic.read_text(encoding="utf-8"))
        validate_structure(data)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: Invalid SSM diagnostic: {exc}", file=sys.stderr)
        return 1

    status = data["Status"]
    response_code = data["ResponseCode"]

    print(f"EXP-001 | SSM status: {status}")
    print(f"EXP-001 | Remote exit code: {response_code}")

    if args.mode == "structure":
        print("EXP-001 | SSM diagnostic structure: VALID")
        return 0

    if status == "Success" and response_code == 0:
        print("EXP-001 | SSM execution: SUCCESS")
        return 0

    if status not in TERMINAL_STATES:
        print(
            f"ERROR: SSM execution not finalized: {status}",
            file=sys.stderr,
        )
    else:
        print(
            f"ERROR: SSM execution failed: "
            f"status={status}, response_code={response_code}",
            file=sys.stderr,
        )

    return 1


if __name__ == "__main__":
    sys.exit(main())
