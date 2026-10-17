#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/config"
AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"; AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"; INSTANCE_PROFILE="${INSTANCE_PROFILE:-LabInstanceProfile}"
PROJECT_TAG="${PROJECT_TAG:-AWS-Cost-SLA-Decision-Agent}"
aws_cli(){ aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }
aws_cli sts get-caller-identity >/dev/null
INSTANCE_ID="$(aws_cli ec2 describe-instances --filters "Name=tag:Project,Values=$PROJECT_TAG" 'Name=tag:Experiment,Values=EXP-002' 'Name=tag:Role,Values=postgresql' 'Name=instance-state-name,Values=pending,running,stopped,stopping' --query 'Reservations[].Instances[] | sort_by(@,&LaunchTime)[-1].InstanceId' --output text)"
[[ "$INSTANCE_ID" == None ]] && INSTANCE_ID=''
if [[ -z "$INSTANCE_ID" ]]; then
  VPC_ID="$(aws_cli ec2 describe-security-groups --filters 'Name=group-name,Values=Lab Instance SG' --query 'SecurityGroups[0].VpcId' --output text)"
  [[ "$VPC_ID" == vpc-* ]] || { echo 'Lab VPC not found' >&2; exit 1; }
  SUBNET_ID="$(aws_cli ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" 'Name=state,Values=available' --query 'sort_by(Subnets,&AvailableIpAddressCount)[-1].SubnetId' --output text)"
  [[ "$SUBNET_ID" == subnet-* ]] || { echo 'Subnet not found' >&2; exit 1; }
  SG_NAME=exp002-postgresql-ssm-only
  SG_ID="$(aws_cli ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=$SG_NAME" --query 'SecurityGroups[0].GroupId' --output text)"
  if [[ "$SG_ID" == None ]]; then
    SG_ID="$(aws_cli ec2 create-security-group --group-name "$SG_NAME" --description 'EXP-002 PostgreSQL SSM only, no ingress' --vpc-id "$VPC_ID" --query GroupId --output text)"
  fi
  INGRESS="$(aws_cli ec2 describe-security-groups --group-ids "$SG_ID" --query 'length(SecurityGroups[0].IpPermissions)' --output text)"
  [[ "$INGRESS" == 0 ]] || { echo 'Security group has inbound rules; aborting' >&2; exit 1; }
  AMI_ID="$(aws_cli ssm get-parameter --name '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64' --query Parameter.Value --output text)"
  echo "About to create EC2: $INSTANCE_TYPE / $AMI_ID / $SUBNET_ID / $SG_ID (AWS charges may apply)" >&2
  [[ "${CONFIRM_CREATE:-}" == YES ]] || { echo 'Set CONFIRM_CREATE=YES to authorize EC2 creation' >&2; exit 2; }
  INSTANCE_ID="$(aws_cli ec2 run-instances --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" --iam-instance-profile "Name=$INSTANCE_PROFILE" --subnet-id "$SUBNET_ID" --security-group-ids "$SG_ID" --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=EXP-002-postgresql},{Key=Project,Value=$PROJECT_TAG},{Key=Experiment,Value=EXP-002},{Key=Role,Value=postgresql}]" --query 'Instances[0].InstanceId' --output text)"
fi
STATE="$(aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text)"
if [[ "$STATE" == stopped ]]; then aws_cli ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null; fi
if [[ "$STATE" == stopping ]]; then aws_cli ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"; aws_cli ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null; fi
aws_cli ec2 wait instance-running --instance-ids "$INSTANCE_ID"
for i in $(seq 1 30); do
  PING="$(aws_cli ssm describe-instance-information --filters "Key=InstanceIds,Values=$INSTANCE_ID" --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || true)"
  [[ "$PING" == Online ]] && break
  sleep 10
done
[[ "${PING:-}" == Online ]] || { echo 'SSM not online' >&2; exit 1; }
printf 'AWS_PROFILE=%q\nAWS_REGION=%q\nINSTANCE_ID=%q\n' "$AWS_PROFILE" "$AWS_REGION" "$INSTANCE_ID" > "$ROOT/config/experiment.env"
chmod 600 "$ROOT/config/experiment.env" 2>/dev/null || true
printf 'INSTANCE_ID=%s\n' "$INSTANCE_ID"
