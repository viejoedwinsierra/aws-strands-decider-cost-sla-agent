# EXP-002 — entrega incremental de ejecución rápida

Este parche se aplica **dentro del repositorio actual**, en `main`. No contiene `.env`, credenciales, datos de S3, modelos ni evidencias. No modifica EXP-001.

## Incluye

- FastAPI con `/health`, `/ready`, `POST /events`, `GET /events/{id}` y consultas reales a PostgreSQL mediante psycopg.
- PostgreSQL y API en la misma EC2, con usuario Linux y rol PostgreSQL `exp002_api` y autenticación peer por socket Unix (sin exponer puerto 5432).
- Locust con carga de escritura/lectura y readiness.
- Dependencia `psycopg[binary]==3.2.6` añadida al paquete de FastAPI.
- `bootstrap_all.sh run` ahora delega a un runner EXP-002 y no ejecuta la lógica EXP-001 heredada.
- El runner EXP-002 genera un RUN_ID único, toma snapshots Linux PRE/RUN/POST por SSM, consulta CloudWatch, ejecuta Locust, normaliza métricas, evalúa SLA, calcula hashes y archiva en S3.
- Prueba local unitaria del normalizador y SLA.

## Límites importantes

**No se ha desplegado ni ejecutado en AWS desde este entorno.** El paquete supera comprobaciones locales de sintaxis y pruebas de normalización. La obtención de métricas CloudWatch puede retrasarse; no se inventan observaciones ausentes. El reporte EXP-002 todavía no está integrado con el contrato histórico de `src.agent.official_integration`, que actualmente está orientado a EXP-001. La telemetría RUN incluye un snapshot durante la carga; PRE y POST duran al menos 60 segundos. No se garantiza granularidad subminuto CloudWatch. No se ha probado la instalación del bundle remoto ni los permisos de la cuenta AWS.

`deploy` crea o reutiliza recursos AWS y puede generar costos; solo ejecutarlo tras validar cuenta, región, permisos y presupuesto. `run` ejecuta cargas reales y consume recursos.

## Validación local

```bash
bash experiments/exp002_component_capacity/infrastructure/preflight_local.sh
python3 -m unittest discover -s experiments/exp002_component_capacity/tests -p test_exp002_runner.py -v
bash -n experiments/exp002_component_capacity/infrastructure/*.sh
git diff --check
```

## Comandos oficiales (requieren cuenta AWS explícita y recursos disponibles)

```bash
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh deploy
bash experiments/exp002_component_capacity/infrastructure/bootstrap_all.sh run
```

El runner se niega a sobrescribir un RUN_ID ya existente. Si una etapa falla, inspeccionar `experiments/exp002_component_capacity/results/<RUN_ID>` y el prefijo S3 antes de reintentar. No ejecutar `cleanup.sh` sin revisar los recursos que eliminará.

## Pendientes para completar todo el contrato InfraVita

1. Validar en EC2 la autenticación peer, dependencias empaquetadas, permisos SSM y S3.
2. Confirmar que el pipeline archiva también evidencia parcial cuando falla una etapa.
3. Normalizar telemetría por instancia y ventana al contrato del agente (CloudWatch + Linux), consolidar campañas y habilitar análisis histórico de EXP-002 por Strands Decider 2B.
4. Verificar integridad remota de cada objeto de evidencia y costos de observabilidad.
