#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$ROOT/config/experiment.env}"
[[ -f "$CONFIG_FILE" ]] || { echo "ERROR: missing $CONFIG_FILE" >&2; exit 1; }
# This is a locally controlled experiment configuration, not a downloaded input.
set -a
# shellcheck disable=SC1090
source "$CONFIG_FILE"
set +a
AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
: "${INSTANCE_ID:?Missing INSTANCE_ID in experiment.env}"
[[ "$INSTANCE_ID" =~ ^i-[a-f0-9]+$ ]] || { echo "ERROR: invalid instance ID" >&2; exit 1; }
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
EVIDENCE_ROOT="${EVIDENCE_ROOT:-$HOME/aws-cost-sla-evidence}"
OUTPUT_DIR="$EVIDENCE_ROOT/EXP-002/$RUN_ID/ec2-baseline"
mkdir -p "$OUTPUT_DIR"
aws_cli() { aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }
command -v aws >/dev/null || { echo 'ERROR: AWS CLI missing' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'ERROR: Python 3 missing' >&2; exit 1; }
aws_cli sts get-caller-identity --query Account --output text >/dev/null
PARAMS_FILE="$(mktemp)"
trap 'rm -f "$PARAMS_FILE"' EXIT
python3 - "$PARAMS_FILE" <<'PY'
import json, pathlib, sys
commands = [
  'set -eu',
  'echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"',
  'echo "host=$(hostname)"',
  'cat /etc/os-release',
  'echo "--- memory_bytes ---"',
  'free -b',
  'echo "--- filesystem_bytes ---"',
  'df -B1 /',
  'echo "--- uptime ---"',
  'uptime',
  'echo "--- cpu_count ---"',
  'nproc',
  'echo "--- loadavg ---"',
  'cat /proc/loadavg',
  'echo "--- cpu_stat ---"',
  'head -n 5 /proc/stat',
  'echo "--- network ---"',
  'cat /proc/net/dev',
]
pathlib.Path(sys.argv[1]).write_text(json.dumps({'commands': commands}))
PY
echo "EXP-002 | Collect EC2 baseline | instance=$INSTANCE_ID run=$RUN_ID" >&2
COMMAND_ID="$(aws_cli ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment 'EXP-002 EC2 baseline before PostgreSQL' \
  --parameters "file://$PARAMS_FILE" \
  --query Command.CommandId --output text)"
printf '%s\n' "$COMMAND_ID" > "$OUTPUT_DIR/ssm_command_id.txt"
if ! aws_cli ssm wait command-executed --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"; then
  echo 'SSM wait did not confirm success; collecting invocation status.' >&2
fi
aws_cli ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --output json > "$OUTPUT_DIR/ssm_invocation.json"
python3 - "$OUTPUT_DIR" "$INSTANCE_ID" "$RUN_ID" <<'PY'
import json, pathlib, sys
from datetime import datetime, timezone
out = pathlib.Path(sys.argv[1])
inv = json.loads((out/'ssm_invocation.json').read_text())
(out/'host_snapshot.txt').write_text(inv.get('StandardOutputContent') or '')
(out/'stderr.txt').write_text(inv.get('StandardErrorContent') or '')
manifest = {
  'schema_version': '1.0', 'experiment_id': 'EXP-002', 'run_id': sys.argv[3],
  'component_id': 'ec2-host', 'instance_id': sys.argv[2],
  'collected_at_utc': datetime.now(timezone.utc).isoformat(),
  'stage': 'before_postgresql', 'source': 'aws_ssm',
  'ssm_command_id': inv.get('CommandId'), 'status': inv.get('Status'),
  'files': ['ssm_invocation.json', 'host_snapshot.txt', 'stderr.txt', 'ssm_command_id.txt']
}
(out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(f"SSM status: {inv.get('Status')}")
print(f"Evidence: {out}")
if inv.get('Status') != 'Success':
  raise SystemExit('ERROR: baseline collection did not succeed; inspect stderr.txt')
PY
