#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/experiment.env"

[[ -f "$CONFIG_FILE" ]] || {
  echo "ERROR: Missing experiment.env" >&2
  exit 1
}

# Preserve parameters supplied by the experiment orchestrator.
RUNNER_USERS="${USERS-}"
RUNNER_SPAWN_RATE="${SPAWN_RATE-}"
RUNNER_DURATION="${DURATION-}"
RUNNER_RUN_ID="${RUN_ID-}"
RUNNER_HTTP_INSTANCE_ID="${HTTP_INSTANCE_ID-}"
RUNNER_LOCUST_INSTANCE_ID="${LOCUST_INSTANCE_ID-}"

set -a
source "$CONFIG_FILE"
set +a

[[ -z "$RUNNER_USERS" ]] || USERS="$RUNNER_USERS"
[[ -z "$RUNNER_SPAWN_RATE" ]] || SPAWN_RATE="$RUNNER_SPAWN_RATE"
[[ -z "$RUNNER_DURATION" ]] || DURATION="$RUNNER_DURATION"
[[ -z "$RUNNER_RUN_ID" ]] || RUN_ID="$RUNNER_RUN_ID"
[[ -z "$RUNNER_HTTP_INSTANCE_ID" ]] || HTTP_INSTANCE_ID="$RUNNER_HTTP_INSTANCE_ID"
[[ -z "$RUNNER_LOCUST_INSTANCE_ID" ]] || LOCUST_INSTANCE_ID="$RUNNER_LOCUST_INSTANCE_ID"

AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"

: "${HTTP_INSTANCE_ID:?}"
: "${LOCUST_INSTANCE_ID:?}"
: "${EVIDENCE_BUCKET:?}"

USERS="${USERS:-5}"
SPAWN_RATE="${SPAWN_RATE:-1}"
DURATION="${DURATION:-60s}"
RUN_ID="${RUN_ID:-private_ec2_$(date -u +%Y%m%dT%H%M%SZ)}"

[[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || {
  echo "ERROR: Invalid RUN_ID" >&2
  exit 1
}

aws_cli() {
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"
}

HTTP_IP="$(aws_cli ec2 describe-instances \
  --instance-ids "$HTTP_INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' \
  --output text)"

[[ "$HTTP_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "ERROR: Invalid HTTP private IP" >&2
  exit 1
}

S3_PREFIX="s3://${EVIDENCE_BUCKET}/experiments/exp001_capacity/results/${RUN_ID}"
LOCAL_DIR="${SCRIPT_DIR}/../results/${RUN_ID}"

# Preserve execution metadata before running Locust.
mkdir -p "$LOCAL_DIR"

SOURCE_COMMIT="$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || true)"
export RUN_ID HTTP_IP USERS SPAWN_RATE DURATION
export HTTP_INSTANCE_ID LOCUST_INSTANCE_ID AWS_REGION SOURCE_COMMIT

python3 "$SCRIPT_DIR/python/generate_run_manifest.py" "$LOCAL_DIR/run_manifest.json"

aws_cli s3 cp \
  "$LOCAL_DIR/run_manifest.json" \
  "$S3_PREFIX/run_manifest.json" \
  --sse AES256 --no-progress

echo "RUN_MANIFEST_UPLOADED"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

python3 "$SCRIPT_DIR/python/generate_ssm_command.py" "$TMP" "$HTTP_IP" "$USERS" "$SPAWN_RATE" "$DURATION" "$RUN_ID" "$S3_PREFIX"

echo "EXP-001 | Load test"
echo "Run ID: $RUN_ID"
echo "Target: http://$HTTP_IP:8080"
echo "Users: $USERS | Spawn rate: $SPAWN_RATE | Duration: $DURATION"

COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$LOCUST_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "EXP-001 load test $RUN_ID" \
  --parameters "file://$TMP" \
  --timeout-seconds 600 \
  --query Command.CommandId \
  --output text)"

echo "SSM Command ID: $COMMAND_ID"

# El waiter estándar de SSM puede terminar antes que una prueba de 60 s.
# Consultamos el estado hasta que la ejecución finalice.
SSM_POLL_TIMEOUT=1
STATUS="Unknown"

for attempt in $(seq 1 120); do
  STATUS="$(aws_cli ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$LOCUST_INSTANCE_ID" \
    --query Status \
    --output text 2>/dev/null || true)"

  case "$STATUS" in
    Success|Failed|Cancelled|TimedOut)
      SSM_POLL_TIMEOUT=0
      break
      ;;
  esac

  if (( attempt < 120 )); then
    sleep 5
  fi
done

if (( SSM_POLL_TIMEOUT != 0 )); then
  echo "ERROR: SSM polling timeout after 120 attempts" >&2
  echo "Last observed SSM status: $STATUS" >&2
fi

mkdir -p "$LOCAL_DIR/diagnostics"

# Store raw SSM diagnostics on the native WSL filesystem.
PRIVATE_ROOT="${HOME}/.local/share/aws-cost-sla-agent/exp001"
PRIVATE_DIR="${PRIVATE_ROOT}/${RUN_ID}"

# Restrict access to all agent-specific storage directories.
(umask 077; mkdir -p "$PRIVATE_DIR")
chmod 700   "${HOME}/.local/share/aws-cost-sla-agent"   "$PRIVATE_ROOT"   "$PRIVATE_DIR"

SSM_DIAGNOSTIC="$PRIVATE_DIR/ssm_locust_execution_original.json"

# Create the raw diagnostic with restrictive permissions.
rm -f -- "$SSM_DIAGNOSTIC"
(umask 077; : > "$SSM_DIAGNOSTIC")
chmod 600 "$SSM_DIAGNOSTIC"

SSM_DIAGNOSTIC_STATUS=0
if ! aws_cli ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$LOCUST_INSTANCE_ID" \
  --query '{Status:Status,ResponseCode:ResponseCode,Output:StandardOutputContent,Errors:StandardErrorContent}' \
  --output json > "$SSM_DIAGNOSTIC"; then
  SSM_DIAGNOSTIC_STATUS=1
  echo "ERROR: Unable to retrieve SSM diagnostic" >&2
fi

# Validate the diagnostic structure before publishing to S3.
if [[ "$SSM_DIAGNOSTIC_STATUS" -eq 0 ]]; then
  python3 "$SCRIPT_DIR/python/validate_ssm_diagnostic.py" \
    "$SSM_DIAGNOSTIC" --mode structure || SSM_DIAGNOSTIC_STATUS=$?
fi

SSM_SANITIZED="$LOCAL_DIR/diagnostics/ssm_locust_execution_sanitized.json"

SSM_SANITIZE_STATUS=1
if [[ "$SSM_DIAGNOSTIC_STATUS" -eq 0 ]]; then
  SSM_SANITIZE_STATUS=0
  python3 "$SCRIPT_DIR/python/sanitize_ssm_diagnostic.py" \
    "$SSM_DIAGNOSTIC" \
    "$SSM_SANITIZED" || SSM_SANITIZE_STATUS=$?
fi

SSM_UPLOAD_STATUS=1
if (( SSM_DIAGNOSTIC_STATUS == 0 && SSM_SANITIZE_STATUS == 0 )); then
  SSM_UPLOAD_STATUS=0
  aws_cli s3 cp \
    "$SSM_SANITIZED" \
    "$S3_PREFIX/diagnostics/ssm_locust_execution.json" \
    --sse AES256 --no-progress || SSM_UPLOAD_STATUS=$?
fi

echo "EXP-001 | Locust SSM status: $STATUS"
echo "EXP-001 | SSM diagnostic: $SSM_DIAGNOSTIC"

if [[ "$SSM_UPLOAD_STATUS" -ne 0 ]]; then
  echo "ERROR: SSM diagnostic upload failed" >&2
fi

# Preserve local evidence even when Locust or SSM reports failure.
mkdir -p "$LOCAL_DIR"

DOWNLOAD_STATUS=0
DOWNLOAD_DIR="$(mktemp -d)"
if aws_cli s3 cp \
  "$S3_PREFIX/" \
  "$DOWNLOAD_DIR/" \
  --recursive \
  --no-progress; then
  cp -R "$DOWNLOAD_DIR/." "$LOCAL_DIR/" || DOWNLOAD_STATUS=$?
else
  DOWNLOAD_STATUS=$?
fi
rm -rf "$DOWNLOAD_DIR"

# Evaluate the remote execution without interrupting evidence recovery.
SSM_EXECUTION_STATUS=0
if [[ "$SSM_DIAGNOSTIC_STATUS" -eq 0 ]]; then
  python3 "$SCRIPT_DIR/python/validate_ssm_diagnostic.py" \
    "$SSM_DIAGNOSTIC" --mode execution || SSM_EXECUTION_STATUS=$?
else
  SSM_EXECUTION_STATUS=1
fi

if (( SSM_POLL_TIMEOUT != 0 )); then
  echo "ERROR: SSM supervision timed out" >&2
  echo "Last observed status: $STATUS" >&2
  echo "Diagnostic: $SSM_DIAGNOSTIC" >&2
  exit 1
fi

if [[ "$STATUS" != "Success" ]]; then
  echo "ERROR: Load test status: $STATUS" >&2
  exit 1
fi

if (( SSM_DIAGNOSTIC_STATUS != 0 ||
      SSM_SANITIZE_STATUS != 0 ||
      SSM_UPLOAD_STATUS != 0 )); then
  echo "ERROR: SSM diagnostic incomplete" >&2
  echo "Retrieval=$SSM_DIAGNOSTIC_STATUS Sanitize=$SSM_SANITIZE_STATUS Upload=$SSM_UPLOAD_STATUS" >&2
  exit 1
fi

if (( SSM_EXECUTION_STATUS != 0 )); then
  echo "ERROR: SSM remote execution validation failed" >&2
  echo "Diagnostic: $SSM_DIAGNOSTIC" >&2
  exit 1
fi

if [[ "$DOWNLOAD_STATUS" -ne 0 ]]; then
  echo "ERROR: Evidence download failed" >&2
  exit 1
fi

[[ -s "$LOCAL_DIR/exp001_stats.csv" ]] || {
  echo "ERROR: Missing Locust statistics CSV" >&2
  exit 1
}

echo "EXP-001 | Load test PASSED"
echo "Local evidence: $LOCAL_DIR"
echo "S3 evidence: $S3_PREFIX/"
