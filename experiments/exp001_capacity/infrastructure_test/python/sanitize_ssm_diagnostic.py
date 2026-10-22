#!/usr/bin/env python3
"""Create a sanitized copy of an EXP-001 SSM diagnostic."""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path


PATTERNS = [
    (
        re.compile(
            r"(?i)(authorization\s*[:=]\s*bearer\s+)"
            r"[^\s,;]+"
        ),
        r"\g<1>[REDACTED]",
    ),
    (
        re.compile(
            r"""(?i)(\b(?:password|secret|api[_-]?key|"""
            r"""access[_-]?token|session[_-]?token)\b"""
            r"""\s*[:=]\s*["']?)[^\s,;"']+"""
        ),
        r"\g<1>[REDACTED]",
    ),
    (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "[REDACTED_AWS_ACCESS_KEY]",
    ),
]

def sanitize(value):
    for pattern, replacement in PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.destination.resolve():
        print("ERROR: Source and destination must differ", file=sys.stderr)
        return 1

    try:
        # Remove stale evidence before reading or validating new input.
        args.destination.unlink(missing_ok=True)

        data = json.loads(args.source.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Diagnostic must be a JSON object")

        for field in ("Status", "ResponseCode", "Output", "Errors"):
            if field not in data:
                raise ValueError(f"Missing field: {field}")

        if not isinstance(data["Status"], str):
            raise ValueError("Status must be a string")

        if type(data["ResponseCode"]) is not int:
            raise ValueError("ResponseCode must be an integer")

        for field in ("Output", "Errors"):
            if not isinstance(data[field], str):
                raise ValueError(f"{field} must be a string")

        sanitized = {
            "Status": data["Status"],
            "ResponseCode": data["ResponseCode"],
            "Output": sanitize(data["Output"]),
            "Errors": sanitize(data["Errors"]),
        }

        args.destination.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=args.destination.parent,
                prefix=".ssm_diagnostic_",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(json.dumps(sanitized, indent=2) + "\n")

            os.replace(temporary_path, args.destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: SSM sanitization failed: {exc}", file=sys.stderr)
        return 1

    print("EXP-001 | SSM diagnostic sanitized")
    return 0


if __name__ == "__main__":
    sys.exit(main())
