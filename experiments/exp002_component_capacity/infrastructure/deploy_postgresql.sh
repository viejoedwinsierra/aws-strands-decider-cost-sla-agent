#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config/experiment.env"
[[ -f "$CONFIG_FILE" ]] || {
  echo "ERROR: Missing EXP-002 config/experiment.env; run provision.sh first" >&2
  exit 1
}
source "$CONFIG_FILE"
AWS_PROFILE="${AWS_PROFILE:-academy-sandbox}"
AWS_REGION="${AWS_REGION:-us-east-1}"
: "${WORKLOAD_INSTANCE_ID:?Missing WORKLOAD_INSTANCE_ID in experiment.env}"
aws_cli(){ aws --profile "$AWS_PROFILE" --region "$AWS_REGION" "$@"; }
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
python3 - "$TMP" "$RUN_ID" <<'PY'
import json,sys
run=sys.argv[2]
cmd=r'''set -eu
E=/var/lib/exp002-evidence/RUN_PLACEHOLDER/postgresql-main
mkdir -p "$E/before" "$E/after" "$E/postgresql"
date -u +%FT%TZ > "$E/before/timestamp.txt"
free -b > "$E/before/memory.txt"
df -B1 / > "$E/before/disk.txt"
cat /proc/loadavg > "$E/before/loadavg.txt"
if ! rpm -q postgresql15-server >/dev/null 2>&1; then dnf install -y postgresql15-server postgresql15; fi
if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then postgresql-setup --initdb; fi
systemctl enable --now postgresql
runuser -u postgres -- psql -X -At -c 'SELECT 1' | grep -qx 1
# Local Unix-socket peer authentication, no database TCP ingress or secrets.
id -u exp002_api >/dev/null 2>&1 || useradd --system --no-create-home --shell /sbin/nologin exp002_api
if ! runuser -u postgres -- psql -X -At -c "SELECT 1 FROM pg_roles WHERE rolname='exp002_api'" | grep -qx 1; then
  runuser -u postgres -- createuser exp002_api
fi
if ! runuser -u postgres -- psql -X -At -c "SELECT 1 FROM pg_database WHERE datname='exp002'" | grep -qx 1; then
  runuser -u postgres -- createdb --owner=exp002_api exp002
fi
runuser -u exp002_api -- psql -X -v ON_ERROR_STOP=1 -d exp002 -c 'CREATE TABLE IF NOT EXISTS events (id BIGSERIAL PRIMARY KEY, payload VARCHAR(256) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())'
runuser -u exp002_api -- psql -X -At -d exp002 -c 'SELECT 1' | grep -qx 1

runuser -u postgres -- psql -X -At -c 'SHOW server_version' > "$E/postgresql/version.txt"
runuser -u postgres -- psql -X -P pager=off -c 'SELECT now(),datname,numbackends,xact_commit,xact_rollback,blks_read,blks_hit FROM pg_stat_database' > "$E/postgresql/database_statistics.txt"
runuser -u postgres -- psql -X -P pager=off -c 'SELECT now(),state,count(*) FROM pg_stat_activity GROUP BY state' > "$E/postgresql/connections.txt"
free -b > "$E/after/memory.txt"
df -B1 / > "$E/after/disk.txt"
cat /proc/loadavg > "$E/after/loadavg.txt"
printf '{"schema_version":"1.0","experiment_id":"EXP-002","run_id":"RUN_PLACEHOLDER","component_id":"postgresql-main","status":"deployed","evidence_path":"%s"}\n' "$E" > "$E/manifest.json"
echo "EVIDENCE_DIR=$E"
'''.replace('RUN_PLACEHOLDER',run)
open(sys.argv[1],'w').write(json.dumps({'commands':[cmd]}))
PY
CID="$(aws_cli ssm send-command --instance-ids "$WORKLOAD_INSTANCE_ID" --document-name AWS-RunShellScript --comment 'EXP-002 PostgreSQL native deploy' --parameters "file://$TMP" --query Command.CommandId --output text)"
echo "SSM_COMMAND_ID=$CID"
aws_cli ssm wait command-executed --command-id "$CID" --instance-id "$WORKLOAD_INSTANCE_ID" || true
aws_cli ssm get-command-invocation --command-id "$CID" --instance-id "$WORKLOAD_INSTANCE_ID" --query '{Status:Status,Output:StandardOutputContent,Errors:StandardErrorContent}' --output json
STATUS="$(aws_cli ssm get-command-invocation --command-id "$CID" --instance-id "$WORKLOAD_INSTANCE_ID" --query Status --output text)"
[[ "$STATUS" == Success ]]
