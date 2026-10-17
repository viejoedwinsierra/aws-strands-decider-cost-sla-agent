# EXP-002 PostgreSQL on EC2 (Amazon Linux 2023)

This package is separate from EXP-001. It uses AWS Academy profile `academy-sandbox`, SSM (no SSH), and an ingress-free security group. AWS EC2/EBS costs may apply.

## Steps from repository root in WSL2

1. Extract ZIP to `experiments/exp002_component_capacity/`.
2. Validate scripts: `bash -n experiments/exp002_component_capacity/exp002_ec2_postgresql/scripts/*.sh`
3. Review EC2 configuration and authorize provisioning explicitly:
   `CONFIRM_CREATE=YES bash experiments/exp002_component_capacity/exp002_ec2_postgresql/scripts/provision_ec2.sh`
4. Only after SSM is Online:
   `bash experiments/exp002_component_capacity/exp002_ec2_postgresql/scripts/deploy_postgresql_ec2.sh`

## Limitations

- PostgreSQL is kept local-only; no public TCP 5432 rule.
- The install script targets Amazon Linux 2023 with PostgreSQL 15 RPMs; verify repository availability in the lab. Existing PostgreSQL clusters are not migrated.
- Telemetry is an initial before/after snapshot saved **on EC2**, not yet continuous or exported to S3. Terminating EC2 can lose it. An evidence export step must follow.
- Config `config/experiment.env` holds an instance ID and should not be committed.
- This is not production hardened: no application DB/user, backup, HA, retention or CloudWatch agent.
