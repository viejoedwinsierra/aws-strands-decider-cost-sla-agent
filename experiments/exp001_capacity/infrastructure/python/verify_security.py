#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/verify_security.sh."""
import json
import os
import subprocess

http = json.loads(os.environ["HTTP_JSON"])["Reservations"][0]["Instances"][0]
locust = json.loads(os.environ["LOCUST_JSON"])["Reservations"][0]["Instances"][0]

assert http["VpcId"] == locust["VpcId"], "Different VPCs"
assert len(http["SecurityGroups"]) == 1, "HTTP must have one SG"
assert len(locust["SecurityGroups"]) == 1, "Locust must have one SG"

http_sg = http["SecurityGroups"][0]["GroupId"]
locust_sg = locust["SecurityGroups"][0]["GroupId"]

cmd = [
    "aws", "--profile", os.environ["AWS_PROFILE"],
    "--region", os.environ["AWS_REGION"],
    "ec2", "describe-security-groups",
    "--group-ids", http_sg, locust_sg,
    "--output", "json",
]
groups = json.loads(subprocess.check_output(cmd, text=True))["SecurityGroups"]
groups = {g["GroupId"]: g for g in groups}

assert groups[http_sg]["GroupName"] == "exp001-http-server-ssm-only"
assert groups[locust_sg]["GroupName"] == "exp001-load-generator-ssm-only"
assert groups[locust_sg]["IpPermissions"] == [], "Locust ingress is not empty"

rules = groups[http_sg]["IpPermissions"]
assert len(rules) == 1, "HTTP must have exactly one ingress rule"

rule = rules[0]
assert rule["IpProtocol"] == "tcp"
assert rule["FromPort"] == rule["ToPort"] == 8080
assert rule.get("IpRanges", []) == []
assert rule.get("Ipv6Ranges", []) == []
assert rule.get("PrefixListIds", []) == []

sources = rule.get("UserIdGroupPairs", [])
assert len(sources) == 1
assert sources[0]["GroupId"] == locust_sg

print("EXP001_SECURITY_VALIDATION_PASSED")
print(f"VPC: {http['VpcId']}")
print(f"HTTP SG: {http_sg}")
print(f"Locust SG: {locust_sg}")
