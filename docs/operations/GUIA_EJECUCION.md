# 05 — Manual de ejecución y reproducción

## Alcance

Dos modos: (A) **auditar resultados históricos sin AWS**; (B) **repetir inferencias sobre el histórico** usando un modelo local o Bedrock. No se requiere desplegar EC2, recrear S3 ni repetir Locust para auditar el cierre.

### A. Auditar el cierre (preferido)

1. Extraer el paquete documental en Ubuntu/WSL.
2. Abrir la carpeta que contiene `sources/`, `compare_reports.py` y `SOURCE_MANIFEST.sha256`.
3. Ejecutar `python scripts/validate_historical_reports.py` para verificar 4 reportes, 20 casos pareados, 40 decisiones y hashes de evidencia entre proveedores.
4. Ejecutar `python compare_reports.py` si desea regenerar las tablas de comparación.
5. Ejecutar `sha256sum -c SOURCE_MANIFEST.sha256` para verificar las fuentes incluidas.
6. Revisar `01_ESTADISTICAS_Y_PRUEBAS.md`, `02_COMPARACION_DE_MODELOS.md` y `HACKATHON_FINAL_REPORT.md`.

### B. Repetir inferencia local en el repositorio

1. `cd /mnt/c/git_edwin/aws-strands-decider-cost-sla-agent`.
2. `source /home/edwin/.venvs/infravita-decider/bin/activate`.
3. `bash scripts/start_agent.sh --check --offline`.
4. Verificar que existan los históricos `experiments/exp001_capacity/results` y `experiments/exp002_component_capacity/results`.
5. Ejecutar los dos comandos de `03_COMANDOS_PRINCIPALES.md` bajo **Inferencia local**.
6. Verificar que cada JSON tenga `total_runs=10` y diez elementos en `decisions`.

### C. Repetir Bedrock (solo si se autorizan nuevas llamadas)

1. Activar el mismo entorno Ubuntu; `python -c 'import boto3'` debe funcionar.
2. Cargar token con `source scripts/load_bedrock_credentials.sh`; la API key es de una cuenta AWS independiente de Academy.
3. Confirmar región `us-east-2` y disponibilidad del modelo sin imprimir credenciales.
4. Ejecutar comandos de **Inferencia Bedrock** en `03_COMANDOS_PRINCIPALES.md`.
5. Comprobar en logs `OFFICIAL_RUNNER_VALIDATED`, archivos JSON y número de decisiones.
6. Regenerar la comparación y comprobar si cambiaron las decisiones; la generación no garantiza salidas idénticas.

### D. Diagnóstico de errores

| Síntoma | Comprobación / acción |
|---|---|
| `ModuleNotFoundError: boto3` | Verificar que el venv activo sea el existente; instalar solo si falta y con aprobación explícita |
| `CalledProcessError` del bridge | Capturar `stderr` de `src.decider.bedrock_bridge`; evitar mostrar secretos |
| Falta `AWS_BEARER_TOKEN_BEDROCK` | Volver a cargar el script de credenciales en la sesión actual |
| Faltan evidencias o `EVIDENCE_BUCKET` | Para inferencia offline, pasar `--local-root` y evitar sincronización S3 |
| Decisión `Insufficient Evidence` | Revisar `sla_status`, calidad y disponibilidad de telemetría y razón del guardrail |
| No coinciden decisiones local/Bedrock | Revisar propuestas y guardrails por RUN_ID; no atribuir automáticamente error a un proveedor |

### E. Protección y custodia

- No versionar claves, `.env`, archivos privados ni logs que puedan contener tokens.
- Preservar `evidence_sha256` y `run_id` al comparar.
- Evitar `git add .` y cualquier comando de despliegue/destrucción en el cierre.
- Mantener separados resultados observados, inferencias y trabajo futuro.
