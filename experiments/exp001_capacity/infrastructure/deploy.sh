#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

echo "EXP-001 | Automated Deployment"

echo "[1/8] Prepare S3"
bash "$SCRIPT_DIR/create_bucket.sh"

echo "[2/8] Prepare Locust dependencies"
bash "$SCRIPT_DIR/prepare_dependencies.sh"

echo "[3/8] Provision HTTP EC2"
INSTANCE_ROLE=http-server bash "$SCRIPT_DIR/provision.sh"

echo "[4/8] Deploy HTTP"
set -a
source "$BASE_DIR/config/experiment.env"
set +a
INSTANCE_ID="$HTTP_INSTANCE_ID" bash "$SCRIPT_DIR/deploy_http.sh"

echo "[5/8] Provision Locust EC2"
INSTANCE_ROLE=load-generator bash "$SCRIPT_DIR/provision.sh"

echo "[6/8] Deploy Locust"
set -a
source "$BASE_DIR/config/experiment.env"
set +a
: "${HTTP_INSTANCE_ID:?Missing HTTP_INSTANCE_ID}"
: "${LOCUST_INSTANCE_ID:?Missing LOCUST_INSTANCE_ID}"
: "${EVIDENCE_BUCKET:?Missing EVIDENCE_BUCKET}"
bash "$SCRIPT_DIR/deploy_locust.sh"

echo "[7/8] Configure private network"
bash "$SCRIPT_DIR/configure_network.sh"

echo "[8/8] Verify infrastructure"
bash "$SCRIPT_DIR/verify_security.sh"
bash "$SCRIPT_DIR/verify.sh"
bash "$SCRIPT_DIR/verify_locust.sh"
bash "$SCRIPT_DIR/verify_network.sh"

echo "EXP-001 | DEPLOYMENT COMPLETED"
