# EXP-002 — Entrega de preflight y hallazgos (23 octubre 2026)

Este paquete es un **parche incremental**, no un segundo repositorio. Copiar sus archivos sobre la raíz de `aws-strands-decider-cost-sla-agent` en `main`, tras revisar el diff. No contiene credenciales ni evidencia histórica.

## Verificado desde `proyecto.zip`

- `bootstrap_all.sh deploy` orquesta S3, dependencias, EC2 workload, PostgreSQL, FastAPI, EC2 Locust, Locust, red y verificadores.
- `bootstrap_all.sh run` es aún código heredado de EXP-001: exige `HTTP_INSTANCE_ID`, usa `exp001_stats.csv` y no debe ejecutarse.
- `run_load.sh`, `analyze_results.sh` y `archive_evidence.sh` contienen rutas/nombres EXP-001 y no conforman un pipeline EXP-002 válido.
- La aplicación FastAPI solo tiene `/health` con respuesta estática. No hay endpoint que consulte PostgreSQL: no se puede medir todavía el SLA de una operación de base de datos.
- `locustfile.py` solo llama `/health`, por lo que las cargas actuales no miden PostgreSQL.
- El archivo `config/experiment.env` contiene identificadores de recursos de una campaña anterior; deben considerarse obsoletos hasta verificar explícitamente la cuenta y los recursos. No asumir que existe infraestructura activa.
- `REPRODUCIBILITY_AND_VALIDATION.md` reconoce que no se hizo despliegue AWS real y que el modo `run` está pendiente.

## Nuevo preflight

`bash experiments/exp002_component_capacity/infrastructure/preflight_local.sh`

Comprueba archivos obligatorios, sintaxis Python y shell, y ejecuta los tests locales existentes. No llama AWS, no descarga paquetes, no instala dependencias ni modifica evidencia.

## Pendiente para un entregable integral

1. Diseño y validación de endpoint FastAPI con consulta PostgreSQL real; instrumentar latencia, errores y throughput por operación.
2. Rehacer `run_load.sh`, `analyze_results.sh`, `archive_evidence.sh` y la rama `run` de bootstrap con nombres EXP-002 y rutas S3 propias.
3. Instrumentar ventanas PRE/RUN/POST CloudWatch y Linux/SSM para ambas EC2, con calidad, origen, timestamps y cobertura verificables.
4. Registrar manifiestos, hashes, SLA y costos computacionales por RUN_ID; evitar sobrescrituras y preservar históricos.
5. Extender contrato de ingestión y guardrails del agente para EXP-002, sin cambiar ni degradar EXP-001.
6. Añadir pruebas offline con fixtures para el ciclo completo y casos de error, reintento, pérdida de telemetría y duplicados.
7. Hacer AWS deploy solo tras autorización explícita, verificación de cuenta/perfil, IAM, S3, red y estimación de costos; limpiar solo recursos identificados como propios.

**No se declara EXP-002 terminado ni desplegado** con este parche: es un control inicial reproducible y un diagnóstico basado en el código recibido.
