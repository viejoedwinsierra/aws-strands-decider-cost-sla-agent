# 03 — Comandos principales (WSL Ubuntu)

**Regla:** ejecutar desde la raíz del repositorio. Los comandos de análisis no requieren desplegar EC2. El flag `--offline` significa *evidencia local*; Bedrock sigue siendo una llamada de red con costo potencial.

## Inicio de sesión

```bash
cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent || exit 1
source /home/edwin/.venvs/infravita-decider/bin/activate
python -c 'import boto3, botocore; print("BEDROCK_SDK_OK", boto3.__version__)'
bash scripts/start_agent.sh --check --offline
```

## Inferencia local sobre histórico (no AWS)

```bash
mkdir -p reports/local_model
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp001_capacity/results \
  --provider local --decision-policy computational-v1 \
  --output reports/local_model/exp001_local.json
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp002_component_capacity/results \
  --provider local --decision-policy computational-v1 \
  --output reports/local_model/exp002_local.json
```

## Inferencia Bedrock (AWS remoto; cuenta separada)

```bash
source scripts/load_bedrock_credentials.sh
mkdir -p reports/bedrock
set -o pipefail
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp001_capacity/results \
  --provider bedrock --decision-policy computational-v1 \
  --output reports/bedrock/exp001_bedrock.json \
  2>&1 | tee reports/bedrock/exp001_execution.log
bash scripts/start_agent.sh --offline --infer \
  --local-root experiments/exp002_component_capacity/results \
  --provider bedrock --decision-policy computational-v1 \
  --output reports/bedrock/exp002_bedrock.json \
  2>&1 | tee reports/bedrock/exp002_execution.log
```

**Seguridad:** el script de credenciales fue usado exitosamente en la sesión reportada, pero no se encuentra en el snapshot anterior del repositorio incluido como fuente; comprobar su existencia local. No imprimir `AWS_BEARER_TOKEN_BEDROCK`, ni usar `set -x`. No activar `AWS_PROFILE=academy-sandbox` al invocar Bedrock.

## Comparación y control sin llamadas AWS

Desde la carpeta de este paquete documental:

```bash
python compare_reports.py
python scripts/validate_historical_reports.py
sha256sum -c SOURCE_MANIFEST.sha256
```

La validación de SHA-256 debe ejecutarse desde el directorio del manifiesto; el script de comparación escribe sus salidas allí. Antes de sobrescribir archivos, hacer copia del paquete si se desea conservar la fotografía original.

## Git seguro

```bash
git status --short
git diff --check
git diff --cached --name-only
```

No ejecutar `git add .`, `git add -A`, `git reset --hard` ni publicar logs con secretos. Ningún comando de esta guía realiza commits o despliegues.
