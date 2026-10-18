#!/usr/bin/env python3
"""Build, merge and validate AWS S3 bucket tags for EXP-001."""

import argparse
import json
import os
import sys


def required_tags():
    """Return the required experiment tags."""
    return {
        "Project": os.environ["PROJECT_TAG"],
        "Experiment": os.environ["EXPERIMENT_ID"],
        "Environment": os.environ["ENVIRONMENT"],
        "ManagedBy": "bootstrap_all",
        "Component": "evidence-storage",
        "Purpose": "experiment-evidence",
    }


def parse_tags(data):
    """Convert an AWS TagSet response into a dictionary."""
    return {
        tag["Key"]: tag["Value"]
        for tag in data.get("TagSet", [])
    }


def format_tags(tags):
    """Convert a dictionary into an AWS TagSet."""
    return {
        "TagSet": [
            {"Key": key, "Value": value}
            for key, value in sorted(tags.items())
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["build", "merge", "validate"])
    args = parser.parse_args()

    expected = required_tags()

    if args.operation == "build":
        print(json.dumps(format_tags(expected)))
        return

    current = parse_tags(json.load(sys.stdin))

    if args.operation == "merge":
        current.update(expected)
        print(json.dumps(format_tags(current)))
        return

    if args.operation == "validate":
        differences = {
            key: {"expected": value, "actual": current.get(key)}
            for key, value in expected.items()
            if current.get(key) != value
        }

        if differences:
            print(json.dumps(differences, indent=2), file=sys.stderr)
            sys.exit(1)

        print("BUCKET_TAG_VALIDATION_PASSED")


if __name__ == "__main__":
    main()
