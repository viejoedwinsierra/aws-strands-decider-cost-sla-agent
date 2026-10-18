#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../config/experiment.env"

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

: "${WORKLOAD_INSTANCE_ID:?}"
: "${LOCUST_INSTANCE_ID:?}"

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

WORKLOAD_JSON="$(aws_cli ec2 describe-instances --instance-ids "$WORKLOAD_INSTANCE_ID" --output json)"
LOCUST_JSON="$(aws_cli ec2 describe-instances --instance-ids "$LOCUST_INSTANCE_ID" --output json)"

WORKLOAD_JSON="$WORKLOAD_JSON" LOCUST_JSON="$LOCUST_JSON" \
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" python3 - <<'PY'
import json
import os
import subprocess

workload = json.loads(os.environ["WORKLOAD_JSON"])["Reservations"][0]["Instances"][0]
locust = json.loads(os.environ["LOCUST_JSON"])["Reservations"][0]["Instances"][0]

assert workload["VpcId"] == locust["VpcId"], "Different VPCs"
assert len(workload["SecurityGroups"]) == 1, "WORKLOAD must have one SG"
assert len(locust["SecurityGroups"]) == 1, "Locust must have one SG"

workload_sg = workload["SecurityGroups"][0]["GroupId"]
locust_sg = locust["SecurityGroups"][0]["GroupId"]

cmd = [
    "aws", "--profile", os.environ["AWS_PROFILE"],
    "--region", os.environ["AWS_REGION"],
    "ec2", "describe-security-groups",
    "--group-ids", workload_sg, locust_sg,
    "--output", "json",
]
groups = json.loads(subprocess.check_output(cmd, text=True))["SecurityGroups"]
groups = {g["GroupId"]: g for g in groups}

assert groups[workload_sg]["GroupName"] == "exp002-workload-server-ssm-only"
assert groups[locust_sg]["GroupName"] == "exp002-load-generator-ssm-only"
assert groups[locust_sg]["IpPermissions"] == [], "Locust ingress is not empty"

rules = groups[workload_sg]["IpPermissions"]
assert len(rules) == 1, "WORKLOAD must have exactly one ingress rule"

rule = rules[0]
assert rule["IpProtocol"] == "tcp"
assert rule["FromPort"] == rule["ToPort"] == 8001
assert rule.get("IpRanges", []) == []
assert rule.get("Ipv6Ranges", []) == []
assert rule.get("PrefixListIds", []) == []

sources = rule.get("UserIdGroupPairs", [])
assert len(sources) == 1
assert sources[0]["GroupId"] == locust_sg

print("EXP002_SECURITY_VALIDATION_PASSED")
print(f"VPC: {workload['VpcId']}")
print(f"WORKLOAD SG: {workload_sg}")
print(f"Locust SG: {locust_sg}")
PY
