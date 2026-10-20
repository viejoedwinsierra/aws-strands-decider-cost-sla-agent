#!/usr/bin/env bash
# EXP-001 | Provision EC2 for HTTP or Locust using project configuration.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_FILE="${SCRIPT_DIR}/../config/project.env"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

# bootstrap_all.sh already exports project variables. Loading the same file
# here also supports direct invocation of provision.sh.
[[ -f "$PROJECT_FILE" ]] || { echo "ERROR: Missing project.env: $PROJECT_FILE" >&2; exit 1; }
set -a
source "$PROJECT_FILE"
set +a

: "${AWS_PROFILE:?Missing AWS_PROFILE in project.env}"
: "${AWS_REGION:?Missing AWS_REGION in project.env}"
: "${PROJECT_TAG:?Missing PROJECT_TAG in project.env}"
: "${EXPERIMENT_ID:?Missing EXPERIMENT_ID in project.env}"

# Defaults remain until project.env defines both provisioning settings.
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
INSTANCE_PROFILE="${INSTANCE_PROFILE:-LabInstanceProfile}"
INSTANCE_ROLE="${INSTANCE_ROLE:-http-server}"
INSTANCE_NAME="${INSTANCE_NAME:-${EXPERIMENT_ID}-${INSTANCE_ROLE}}"
# Preserve the existing SG naming contract to reuse deployed resources.
SG_NAME="${SG_NAME:-exp001-${INSTANCE_ROLE}-ssm-only}"

aws_cli() { aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

command -v aws >/dev/null || fail "AWS CLI no instalado"
command -v python3 >/dev/null || fail "Python 3 no instalado"

printf '%s | Provision | profile=%s region=%s\n' "$EXPERIMENT_ID" "$AWS_PROFILE" "$AWS_REGION" >&2
aws_cli sts get-caller-identity --query Account --output text >/dev/null || fail "Credenciales expiradas o sin autorizacion"

# Reuse an existing instance, but only if both ownership tags match.
INSTANCE_ID="$(aws_cli ec2 describe-instances \
  --filters "Name=tag:Project,Values=$PROJECT_TAG" "Name=tag:Experiment,Values=$EXPERIMENT_ID" "Name=tag:Role,Values=$INSTANCE_ROLE" \
            'Name=instance-state-name,Values=pending,running,stopping,stopped' \
  --query 'Reservations[].Instances[] | sort_by(@,&LaunchTime)[-1].InstanceId' --output text)"
[[ "$INSTANCE_ID" == "None" ]] && INSTANCE_ID=""

if [[ -z "$INSTANCE_ID" ]]; then
  # Use the lab-managed VPC associated with the lab SG; do not create a new VPC.
  VPC_ID="$(aws_cli ec2 describe-security-groups \
    --filters 'Name=group-name,Values=Lab Instance SG' \
    --query 'SecurityGroups[0].VpcId' --output text)"
  [[ -n "$VPC_ID" && "$VPC_ID" != "None" ]] || fail "No se encontro VPC del laboratorio (Lab Instance SG)"

  SUBNET_ID="$(aws_cli ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" 'Name=state,Values=available' \
    --query 'sort_by(Subnets,&AvailableIpAddressCount)[-1].SubnetId' --output text)"
  [[ -n "$SUBNET_ID" && "$SUBNET_ID" != "None" ]] || fail "No hay subnet disponible en $VPC_ID"

  # Prefer a dedicated SG with zero ingress; create it if missing.
  SG_ID="$(aws_cli ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=$SG_NAME" \
    --query 'SecurityGroups[0].GroupId' --output text)"
  if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
    SG_ID="$(aws_cli ec2 create-security-group \
      --group-name "$SG_NAME" --description 'EXP-001 SSM only; no inbound rules' \
      --vpc-id "$VPC_ID" --query GroupId --output text)" || fail "No se pudo crear SG; revisar permisos del Sandbox"
  fi
  INGRESS_COUNT="$(aws_cli ec2 describe-security-groups --group-ids "$SG_ID" \
    --query 'length(SecurityGroups[0].IpPermissions)' --output text)"
  [[ "$INGRESS_COUNT" == "0" ]] || fail "El SG $SG_ID tiene reglas de entrada; no se usara"

  AMI_ID="$(aws_cli ssm get-parameter \
    --name '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64' \
    --query 'Parameter.Value' --output text)" || fail "No se pudo resolver la AMI AL2023"
  [[ -n "$AMI_ID" && "$AMI_ID" != "None" ]] || fail "AMI invalida"

  echo "Creando EC2: AMI=$AMI_ID subnet=$SUBNET_ID sg=$SG_ID" >&2
  INSTANCE_ID="$(aws_cli ec2 run-instances \
    --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" \
    --iam-instance-profile "Name=$INSTANCE_PROFILE" \
    --subnet-id "$SUBNET_ID" --security-group-ids "$SG_ID" \
    --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME},{Key=Project,Value=$PROJECT_TAG},{Key=Experiment,Value=$EXPERIMENT_ID},{Key=Role,Value=$INSTANCE_ROLE}]" \
    --query 'Instances[0].InstanceId' --output text)" || fail "EC2 RunInstances rechazado; revisar permisos, perfil y limites"
  echo "EC2 creada: $INSTANCE_ID" >&2
else
  echo "Reutilizando EC2: $INSTANCE_ID" >&2

  SG_DETAILS="$(aws_cli ec2 describe-instances     --instance-ids "$INSTANCE_ID"     --query 'Reservations[0].Instances[0].SecurityGroups[].[GroupId,GroupName]'     --output text)"

  SG_COUNT="$(printf '%s\n' "$SG_DETAILS" | grep -c '^sg-' || true)"
  [[ "$SG_COUNT" == "1" ]] || fail "La EC2 debe tener exactamente un Security Group"

  SG_ID="$(printf '%s\n' "$SG_DETAILS" | awk '{print $1}')"
  ACTUAL_SG_NAME="$(printf '%s\n' "$SG_DETAILS" | cut -f2-)"

  [[ "$ACTUAL_SG_NAME" == "$SG_NAME" ]] ||     fail "Security Group inesperado: $ACTUAL_SG_NAME (esperado: $SG_NAME)"
fi

STATE="$(aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].State.Name' --output text)"
if [[ "$STATE" == "stopped" ]]; then
  aws_cli ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
elif [[ "$STATE" == "stopping" ]]; then
  aws_cli ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
  aws_cli ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
elif [[ "$STATE" != "running" && "$STATE" != "pending" ]]; then
  fail "Estado de EC2 inesperado: $STATE"
fi
aws_cli ec2 wait instance-running --instance-ids "$INSTANCE_ID"

# SSM agent must be online before deploying.
echo 'Esperando SSM Online (hasta 5 minutos)...' >&2
SSM_ONLINE=0
for attempt in $(seq 1 30); do
  STATUS="$(aws_cli ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || true)"
  if [[ "$STATUS" == "Online" ]]; then SSM_ONLINE=1; break; fi
  sleep 10
done
[[ "$SSM_ONLINE" == "1" ]] || fail "SSM no esta Online; revisar subnet, endpoints/NAT y LabInstanceProfile"

# Atomically update local experiment.env without committing session-specific IDs.
mkdir -p "$(dirname "$CONFIG_FILE")"
CONFIG_FILE="$CONFIG_FILE" INSTANCE_ID="$INSTANCE_ID" INSTANCE_ROLE="$INSTANCE_ROLE" AWS_PROFILE="$AWS_PROFILE" \
AWS_REGION="$AWS_REGION" PROJECT_TAG="$PROJECT_TAG" EXPERIMENT_ID="$EXPERIMENT_ID" \
python3 "$SCRIPT_DIR/python/update_instance_config.py"

# stdout contract: exactly one instance ID; diagnostics go to stderr.
printf '%s\n' "$INSTANCE_ID"
