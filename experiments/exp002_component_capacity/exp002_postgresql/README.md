# EXP-002 — PostgreSQL nativo

Este paquete contiene el primer despliegue de PostgreSQL con captura de evidencia local.

## Copiar desde Windows a WSL2

Descarga el ZIP en Windows y, desde WSL2, ejecuta (ajusta el nombre de usuario Windows):

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent
unzip -o /mnt/c/Users/TU_USUARIO/Downloads/exp002_postgresql.zip -d experiments/exp002_component_capacity
bash -n experiments/exp002_component_capacity/scripts/deploy_postgresql.sh
```

Para ejecutar (requiere sudo, instala paquetes y modifica el sistema **donde se ejecuta**):

```bash
bash experiments/exp002_component_capacity/scripts/deploy_postgresql.sh
```

**Nota:** la evidencia se guarda por defecto en `~/aws-cost-sla-evidence/EXP-002/<run_id>/postgresql-main/`.
El script no configura acceso remoto, ni crea usuarios o bases de datos de aplicación, ni publica en S3.
Las mediciones son snapshots iniciales, no monitoreo periódico.
