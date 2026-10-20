#!/usr/bin/env python3
"""Shared AWS resource tagging contract."""

import argparse
import json
import os
import sys


REQUIRED_KEYS = (
    "Name",
    "Project",
    "Experiment",
    "Environment",
    "ManagedBy",
    "Role",
)

SUPPORTED_RESOURCE_TYPES = (
    "instance",
    "volume",
    "security-group",
)


def build_tags(name, role):
    """Build the common tagging contract."""
    values = {
        "Name": name,
        "Project": os.environ.get("PROJECT_TAG", ""),
        "Experiment": os.environ.get("EXPERIMENT_ID", ""),
        "Environment": os.environ.get("ENVIRONMENT", ""),
        "ManagedBy": os.environ.get("MANAGED_BY", ""),
        "Role": role,
    }

    missing = [key for key in REQUIRED_KEYS if not values[key]]

    if missing:
        raise ValueError(
            f"Missing required tagging values: {', '.join(missing)}"
        )

    return [
        {"Key": key, "Value": values[key]}
        for key in REQUIRED_KEYS
    ]


def build_tag_specifications(resource_types, name, role):
    """Build AWS CLI tag specifications."""
    tags = build_tags(name, role)

    return [
        {
            "ResourceType": resource_type,
            "Tags": tags,
        }
        for resource_type in resource_types
    ]


def validate_tags(actual_tags, expected_tags):
    """Return missing or mismatched tags, rejecting malformed input."""

    def to_mapping(tags, source):
        if not isinstance(tags, list):
            raise ValueError(f"{source} tags must be a JSON array")

        mapping = {}

        for index, item in enumerate(tags):
            if not isinstance(item, dict):
                raise ValueError(
                    f"{source} tag at index {index} must be an object"
                )

            key = item.get("Key")
            value = item.get("Value")

            if not isinstance(key, str) or not key:
                raise ValueError(f"{source} tag has an invalid Key")

            if not isinstance(value, str):
                raise ValueError(f"{source} tag {key} has an invalid Value")

            if key in mapping:
                raise ValueError(f"{source} contains duplicate tag: {key}")

            mapping[key] = value

        return mapping

    actual = to_mapping(actual_tags, "Actual")
    expected = to_mapping(expected_tags, "Expected")

    return {
        key: {
            "expected": value,
            "actual": actual.get(key),
        }
        for key, value in expected.items()
        if actual.get(key) != value
    }

def classify_tag_differences(actual_tags, expected_tags):
    differences = validate_tags(actual_tags, expected_tags)

    missing = {}
    mismatched = {}

    for key, values in differences.items():
        if values["actual"] is None:
            missing[key] = values["expected"]
        else:
            mismatched[key] = values

    return {
        "valid": not differences,
        "missing": missing,
        "mismatched": mismatched,
    }


def s3_expected_tags(name, role):
    """Build the shared contract plus S3-specific tags."""
    tags = build_tags(name, role)
    tags.extend([
        {"Key": "Component", "Value": "evidence-storage"},
        {"Key": "Purpose", "Value": "experiment-evidence"},
    ])
    return tags


def s3_tag_set(tags):
    """Format tags for AWS S3 put-bucket-tagging."""
    return {"TagSet": sorted(tags, key=lambda tag: tag["Key"])}


def s3_main(argv):
    """Build, merge or validate S3 bucket tags."""
    parser = argparse.ArgumentParser(description="S3 bucket tagging")
    parser.add_argument("operation", choices=["build", "merge", "validate", "check-identity"])
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args(argv)

    expected = s3_expected_tags(args.name, args.role)

    if args.operation == "build":
        print(json.dumps(s3_tag_set(expected), separators=(",", ":")))
        return 0

    data = json.load(sys.stdin)
    if not isinstance(data, dict) or not isinstance(data.get("TagSet"), list):
        raise ValueError("S3 input must contain a TagSet array")

    actual = data["TagSet"]
    # Validate structure and reject duplicate keys before merging.
    validate_tags(actual, [])

    if args.operation == "check-identity":
        identity_keys = {
            "Project", "Experiment", "Environment", "ManagedBy"
        }
        identity_tags = [
            tag for tag in expected if tag["Key"] in identity_keys
        ]
        differences = validate_tags(actual, identity_tags)
        if differences:
            print(json.dumps(differences, indent=2), file=sys.stderr)
            return 1
        print("BUCKET_IDENTITY_VALIDATION_PASSED")
        return 0

    if args.operation == "merge":
        merged = {tag["Key"]: tag["Value"] for tag in actual}
        merged.update({tag["Key"]: tag["Value"] for tag in expected})
        result = [{"Key": key, "Value": value}
                  for key, value in merged.items()]
        print(json.dumps(s3_tag_set(result), separators=(",", ":")))
        return 0

    differences = validate_tags(actual, expected)
    if differences:
        print(json.dumps(differences, indent=2), file=sys.stderr)
        return 1

    print("BUCKET_TAG_VALIDATION_PASSED")
    return 0

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "s3":
        return s3_main(sys.argv[2:])

    # Preserve the existing CLI for tag generation.
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        parser = argparse.ArgumentParser(
            description="Validate AWS resource tags"
        )
        parser.add_argument("command", choices=["validate"])
        parser.add_argument("--name", required=True)
        parser.add_argument("--role", required=True)
        parser.add_argument("--actual-tags-file", required=True)

        args = parser.parse_args()

        expected_tags = build_tags(args.name, args.role)

        try:
            with open(args.actual_tags_file, encoding="utf-8") as file:
                actual_tags = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read tags file: {exc}") from exc

        if not isinstance(actual_tags, list):
            raise ValueError("Actual tags must be a JSON array")

        result = classify_tag_differences(actual_tags, expected_tags)
        print(json.dumps(result, separators=(",", ":")))

        return 0 if result["valid"] else 1

    # Existing tag generation interface.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resource-types",
        nargs="+",
        choices=SUPPORTED_RESOURCE_TYPES,
        required=True,
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", required=True)

    args = parser.parse_args()

    specifications = build_tag_specifications(
        args.resource_types,
        args.name,
        args.role,
    )

    print(json.dumps(specifications, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)