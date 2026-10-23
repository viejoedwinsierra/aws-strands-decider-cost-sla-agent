# 04 — Catálogo de scripts y validaciones

La existencia de scripts de infraestructura se contrastó con el snapshot del repositorio `prrroyecto_cierre.zip` (23 octubre 2026); el código local puede haber cambiado después. **No se ejecutaron despliegues ni pruebas de carga al elaborar esta documentación.**

| Script oficial | Función / modo confirmado | Condiciones |
|---|---|---|
| `scripts/start_agent.sh` | `--check`, `--offline --infer`, `--provider local|bedrock` como argumentos del módulo de integración | Reutiliza `INFRAVITA_PYTHON` o venv predeterminado; `--offline` no evita invocar Bedrock |
| `scripts/setup_agent.sh` | `--check`, `--install-missing`, `--install-all`, `--with-dev`, `--offline` | Instalación solo por solicitud; nunca instala PyTorch automáticamente |
| `scripts/sync_evidence.sh` | Sincronización de evidencias | Requiere configuración/credenciales AWS; no usar para cierre local |
| `scripts/analyze.sh` | Análisis de evidencias | Revisar argumentos en la versión local antes de invocar |
| `experiments/exp001_capacity/infrastructure/bootstrap_all.sh` | `deploy`, `run` | **AWS activo requerido**; el modo por defecto es `run`, evitar invocación sin argumento |
| `experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh` | `deploy`, `resume`, `verify`, `run` | **AWS activo requerido**; `run --dry-run` para validación de secuencia |
| `experiments/exp001_capacity/infrastructure_test/run.sh` | Campaña, `--dry-run`, `--sequence-config` | Carga `experiment.env` incluso antes del dry-run en el snapshot: puede requerir `EVIDENCE_BUCKET` |
| `experiments/exp002_component_capacity/infrastructure_test/run.sh` | `--dry-run`, `--execute`, `--sequence-config` | Dry-run evita cargar perfiles AWS; `--execute` requiere recursos |
| `experiments/*/infrastructure/verify.sh` | Verificación de infraestructura | Requiere infraestructura desplegada |
| `experiments/*/infrastructure/verify_security.sh` | Seguridad | Requiere recursos y credenciales apropiadas |
| `experiments/*/infrastructure/verify_network.sh` | Red | Requiere recursos desplegados |
| `experiments/*/infrastructure/verify_locust.sh` | Locust | Requiere generador operativo |
| `experiments/exp002_component_capacity/infrastructure/verify_all.sh` | Preflight EXP-002 | Requiere recursos desplegados |
| `src/agent/official_integration.py` | Descubrimiento histórico, inferencia, guardrails, reportes | Usar a través del runner oficial |
| `src/decider/bedrock_bridge.py` | Invocación Bedrock | Requiere `boto3`, token, acceso al modelo |
| `src/decider/decision_guardrail.py` | Reglas deterministas | No sustituir estado SLA con texto del modelo |
| `compare_reports.py` | Comparación local de cuatro reportes | No AWS ni paquetes externos |
| `scripts/validate_historical_reports.py` (este paquete) | Validación offline de reportes y paridad | No AWS, no modifica fuentes |

## Validación offline recomendada

```bash
cd /ruta/al/paquete/infravita_documentacion_final
python scripts/validate_historical_reports.py
python compare_reports.py
sha256sum -c SOURCE_MANIFEST.sha256
```

## Validaciones de campañas futuras (NO ejecutar para el cierre actual)

```bash
# Revisar configuración antes de cualquier operación AWS
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh run --dry-run
# EXP-001: revisar primero experiment.env, pues su runner puede exigir variables AWS incluso en dry-run
bash experiments/exp001_capacity/infrastructure_test/run.sh --dry-run
```

Para desplegar o correr campañas reales se requiere una aprobación operativa separada, un presupuesto y una infraestructura AWS existente o autorizada. No se documentan comandos de despliegue como parte del procedimiento de cierre offline.
