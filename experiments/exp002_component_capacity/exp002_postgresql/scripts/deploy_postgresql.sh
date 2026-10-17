#!/usr/bin/env bash
set -Eeuo pipefail

# EXP-002: Native PostgreSQL deployment on Ubuntu/Debian.
# Execute on the intended host. Requires sudo and apt access.
EXPERIMENT_ID="${EXPERIMENT_ID:-EXP-002}"
COMPONENT_ID="${COMPONENT_ID:-postgresql-main}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$HOME/aws-cost-sla-evidence/$EXPERIMENT_ID/$RUN_ID/$COMPONENT_ID}"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
fail() { log "ERROR: $*" >&2; exit 1; }

[[ -f /etc/os-release ]] || fail 'Cannot detect operating system'
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu || "${ID:-}" == debian ]] || fail 'Requires Ubuntu or Debian'
command -v sudo >/dev/null || fail 'sudo is required'
command -v apt-get >/dev/null || fail 'apt-get is required'

mkdir -p "$EVIDENCE_DIR"/{before,after,postgresql}
collect_host() {
  local stage="$1" out="$EVIDENCE_DIR/$1/host_snapshot.txt"
  {
    printf 'timestamp_utc=%s\n' "$(date -u +%FT%TZ)"
    printf 'host=%s\n' "$(hostname)"
    printf 'os=%s\n' "${PRETTY_NAME:-unknown}"
    printf '\n== memory ==\n'; free -b
    printf '\n== disk ==\n'; df -B1 /
    printf '\n== load ==\n'; uptime
    printf '\n== cpu ==\n'; nproc
    printf '\n== process snapshot ==\n'; ps -eo pid,comm,%cpu,rss --sort=-rss | head -n 30
  } > "$out"
}

log "Evidence: $EVIDENCE_DIR"
collect_host before

# Check server packages, not only the psql client.
if ! command -v pg_lsclusters >/dev/null 2>&1 || ! dpkg-query -W -f='${Status}' postgresql 2>/dev/null | grep -q 'install ok installed'; then
  log 'Installing PostgreSQL server and client'
  sudo apt-get update
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-client
else
  log 'PostgreSQL server metapackage already installed'
fi

command -v pg_lsclusters >/dev/null || fail 'pg_lsclusters missing after installation'
pg_lsclusters > "$EVIDENCE_DIR/postgresql/clusters_before.txt"
cluster_found=false
while read -r version cluster port status owner rest; do
  [[ "$version" == Ver ]] && continue
  cluster_found=true
  if [[ "$status" != online ]]; then
    log "Starting PostgreSQL cluster $version/$cluster"
    sudo pg_ctlcluster "$version" "$cluster" start
  fi
done < <(pg_lsclusters)
[[ "$cluster_found" == true ]] || fail 'No PostgreSQL cluster found'
pg_lsclusters > "$EVIDENCE_DIR/postgresql/clusters_after.txt"

sudo -u postgres psql -X -At -c 'SELECT 1;' | grep -qx 1 || fail 'PostgreSQL health check failed'
sudo -u postgres psql -X -At -c 'SHOW server_version;' > "$EVIDENCE_DIR/postgresql/version.txt"
sudo -u postgres psql -X -P pager=off -c 'SELECT now(), datname, numbackends, xact_commit, xact_rollback, blks_read, blks_hit FROM pg_stat_database;' > "$EVIDENCE_DIR/postgresql/database_statistics.txt"
sudo -u postgres psql -X -P pager=off -c 'SELECT now(), state, count(*) FROM pg_stat_activity GROUP BY state;' > "$EVIDENCE_DIR/postgresql/connections.txt"
sudo -u postgres psql -X -At -c 'SHOW max_connections;' > "$EVIDENCE_DIR/postgresql/max_connections.txt"
ps -eo pid,comm,%cpu,rss,args | grep '[p]ostgres' > "$EVIDENCE_DIR/postgresql/processes.txt" || true
collect_host after

# Generate JSON safely without shell interpolation into JSON strings.
python3 - "$EVIDENCE_DIR" "$EXPERIMENT_ID" "$RUN_ID" "$COMPONENT_ID" <<'PY'
import json, os, socket, sys
from datetime import datetime, timezone
path, experiment_id, run_id, component_id = sys.argv[1:]
manifest = {
    'schema_version': '1.0', 'experiment_id': experiment_id,
    'run_id': run_id, 'component_id': component_id,
    'component_type': 'postgresql', 'deployment_type': 'native',
    'host': socket.gethostname(),
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'telemetry': {'host_before': 'before/host_snapshot.txt',
                  'host_after': 'after/host_snapshot.txt',
                  'postgresql': 'postgresql/'},
    'status': 'deployed'
}
with open(os.path.join(path, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)
    f.write('\n')
PY
log 'PostgreSQL deployment and initial evidence completed'
log "Evidence: $EVIDENCE_DIR"
