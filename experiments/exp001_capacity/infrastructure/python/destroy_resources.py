#!/usr/bin/env python3
"""Discover and destroy experiment-owned EC2 instances and security groups by tags."""
import argparse
import json
import os
import subprocess
import sys
import time


def aws(*args):
    command = ["aws", "--profile", os.environ["AWS_PROFILE"], "--region", os.environ["AWS_REGION"], *args, "--output", "json", "--no-cli-pager"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"AWS CLI {' '.join(args[:2])}: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def tags(resource):
    return {item["Key"]: item["Value"] for item in resource.get("Tags", [])}


def owned(resource, project, experiment):
    t = tags(resource)
    return t.get("Project") == project and t.get("Experiment") == experiment


def discover(project, experiment):
    filters = ["--filters", f"Name=tag:Project,Values={project}", f"Name=tag:Experiment,Values={experiment}"]
    instances = [instance for reservation in aws("ec2", "describe-instances", *filters).get("Reservations", []) for instance in reservation.get("Instances", [])]
    groups = aws("ec2", "describe-security-groups", *filters).get("SecurityGroups", [])
    if any(not owned(item, project, experiment) for item in instances + groups):
        raise RuntimeError("Ownership check failed; refusing changes")
    return instances, groups


def group_dependencies(group_id):
    enis = aws("ec2", "describe-network-interfaces", "--filters", f"Name=group-id,Values={group_id}").get("NetworkInterfaces", [])
    return [{"id": eni["NetworkInterfaceId"], "status": eni.get("Status"), "instance": eni.get("Attachment", {}).get("InstanceId")} for eni in enis]


def group_references(group_id):
    # Check all security groups in the VPC for ingress/egress references to this group.
    group = aws("ec2", "describe-security-groups", "--group-ids", group_id)["SecurityGroups"][0]
    vpc_id = group["VpcId"]
    all_groups = aws("ec2", "describe-security-groups", "--filters", f"Name=vpc-id,Values={vpc_id}").get("SecurityGroups", [])
    refs = []
    for other in all_groups:
        if other["GroupId"] == group_id:
            continue
        for direction in ("IpPermissions", "IpPermissionsEgress"):
            for rule in other.get(direction, []):
                if any(pair.get("GroupId") == group_id for pair in rule.get("UserIdGroupPairs", [])):
                    refs.append({"group": other["GroupId"], "direction": direction})
    return refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    project = os.environ["PROJECT_TAG"].strip()
    experiment = os.environ["EXPERIMENT_ID"].strip()
    if not project or not experiment or project == "*" or experiment == "*":
        raise ValueError("Explicit non-wildcard Project and Experiment tags are required")
    account = aws("sts", "get-caller-identity")["Account"]
    expected_account = os.environ.get("AWS_ACCOUNT_ID", "").strip()
    if expected_account and expected_account != account:
        raise ValueError(f"Account mismatch: expected {expected_account}, got {account}")
    print(f"Account={account} Region={os.environ['AWS_REGION']} Profile={os.environ['AWS_PROFILE']}")
    print(f"Scope: Project={project} Experiment={experiment}")
    instances, groups = discover(project, experiment)
    active = [i for i in instances if i["State"]["Name"] not in ("terminated", "shutting-down")]
    print("\nEC2 instances:")
    for instance in instances:
        print(f"  {instance['InstanceId']} state={instance['State']['Name']} name={tags(instance).get('Name', '-')}")
    if not instances:
        print("  none")
    print("\nSecurity groups:")
    for group in groups:
        print(f"  {group['GroupId']} name={group['GroupName']} ingress={len(group.get('IpPermissions', []))} egress={len(group.get('IpPermissionsEgress', []))}")
    if not groups:
        print("  none")
    print(f"\nPlan: terminate {len(active)} EC2 instance(s); delete {len(groups)} security group(s). S3/VPC/subnets/IAM untouched.")
    if args.dry_run:
        for group in groups:
            print(f"  SG {group['GroupId']} current ENI dependencies: {group_dependencies(group['GroupId'])}")
            print(f"  SG {group['GroupId']} references from other SGs: {group_references(group['GroupId'])}")
        print("DRY RUN: no changes made")
        return
    if active:
        ids = [i["InstanceId"] for i in active]
        print("Terminating: " + ", ".join(ids), flush=True)
        aws("ec2", "terminate-instances", "--instance-ids", *ids)
        waiter = subprocess.run(["aws", "--profile", os.environ["AWS_PROFILE"], "--region", os.environ["AWS_REGION"], "ec2", "wait", "instance-terminated", "--instance-ids", *ids], check=False)
        if waiter.returncode:
            raise RuntimeError("Instance termination wait failed; stop before deleting SGs")
    # Fresh discovery prevents deletion if the tags or scope have changed.
    _, current_groups = discover(project, experiment)
    failures = []
    for group in current_groups:
        group_id = group["GroupId"]
        enis = group_dependencies(group_id)
        refs = group_references(group_id)
        if enis or refs:
            print(f"SKIP {group_id}: dependencies ENIs={enis} SG-references={refs}")
            failures.append(group_id)
            continue
        try:
            aws("ec2", "delete-security-group", "--group-id", group_id)
            print(f"DELETED SG {group_id} (ingress and egress rules removed with group)")
        except RuntimeError as exc:
            print(f"FAILED SG {group_id}: {exc}")
            failures.append(group_id)
    if failures:
        raise RuntimeError("Some SGs were retained due to dependencies/errors: " + ", ".join(failures))
    print("SUCCESS: tagged EC2/SG cleanup complete. Shared resources and S3 untouched.")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
