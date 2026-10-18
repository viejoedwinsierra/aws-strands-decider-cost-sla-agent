# EXP-002 FastAPI / LB-03

Independent, SSM-based FastAPI deployment to an existing EC2. Python 3.9 supported via pinned FastAPI 0.115.6 and Uvicorn 0.34.0. This package does not install, connect to, or restart PostgreSQL. The API binds to 127.0.0.1 only.

## Usage (from WSL2)

```bash
./scripts/deploy_api_ec2.sh --instance-id i-05d1996ebedd80865 --app-name exp002-fastapi --port 8001 --mode standalone --profile academy-sandbox --region us-east-1
```

Prerequisites: SSM-managed EC2, Python 3.9 with `venv` and pip available, network access from the EC2 to install pinned Python dependencies. The script is non-destructive to PostgreSQL, but **will replace and restart a previously deployed service with the same app name**. Choose a unique app name per application. Do not use an already-occupied port.

Deployment evidence is saved locally under `~/aws-cost-sla-evidence/EXP-002/<run_id>/deployments/<app_name>/` and on EC2 under `/var/lib/exp002-evidence/<run_id>/fastapi/<app_name>/`. The script captures a deployment verification, not the LB-03 steady-state measurement. Collect the latter separately after deployment and stabilization.

## Scope

LB-03 only. LB-04 PostgreSQL integration and baseline collection are deliberately not included in this first deployment package.
