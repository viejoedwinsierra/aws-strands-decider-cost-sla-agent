# InfraVita V2 — Informe de cierre técnico y experimental

**Fecha de corte:** 23 de octubre de 2026
**Evento:** Agent Experience Hackathon — Strands Decider 2B
**Estado:** cierre de la implementación experimental; documentación para revisión y entrega. No equivale a confirmación de publicación o envío al evento.

## Resumen ejecutivo

InfraVita V2 es un prototipo de apoyo a decisiones sobre capacidad, eficiencia computacional y riesgo de SLA a partir de evidencias históricas de infraestructura y carga. El alcance experimental implementado incluye EXP-001 (servicio HTTP) y EXP-002 (FastAPI + PostgreSQL), dos campañas por experimento y cinco escenarios de carga por campaña. Se ejecutaron **20 casos de inferencia con el modelo local Strands Decider 2B v21 y 20 con Amazon Bedrock (Amazon Nova Micro)**: 40 inferencias con estado de ejecución exitoso. No se realizaron cambios de capacidad en AWS como resultado de las decisiones.

El proyecto separa tres niveles: **evidencia observada**, **recomendación probabilística o generativa** y **decisión efectiva gobernada por reglas**. Esta distinción constituye el resultado principal: las propuestas del modelo pueden ser rechazadas si falta evidencia de SLA o de recursos.

## Arquitectura y fuentes

1. Generación de carga y experimentos: Locust, HTTP, FastAPI y PostgreSQL sobre EC2.
2. Captura: métricas CloudWatch y snapshots Linux vía AWS Systems Manager; resultados normalizados de carga. Evidencias archivadas en S3 durante la ejecución experimental y reutilizadas localmente para el análisis de cierre.
3. Integración: runner oficial `scripts/start_agent.sh` y módulo `src.agent.official_integration`; selección de proveedor `local` o `bedrock`.
4. Inferencia: Strands Decider 2B v21 local y Amazon Nova Micro mediante Amazon Bedrock (`us.amazon.nova-micro-v1:0`, región `us-east-2`).
5. Gobernanza: `computational-v1` valida la propuesta frente al estado oficial de SLA y las evidencias disponibles.
6. Salida: JSON con `run_id`, `evidence_sha256`, métricas, recomendación, razones, guardrail y decisión efectiva.

**Aislamiento de credenciales:** la lectura de evidencias de AWS Academy y la invocación de Bedrock en cuenta independiente no deben mezclar perfiles. Ninguna API key, token o credencial debe incorporarse al repositorio, informes o logs públicos. `--offline` en este flujo describe lectura local de evidencias; con `--provider bedrock` sí se invoca el servicio remoto.

## Cobertura de los reportes

| Experimento | Casos únicos | CloudWatch | Linux SSM | SLA oficial |
|---|---:|---:|---:|---|
| EXP-001 | 10 | 580 | 42 | 10 PASS |
| EXP-002 | 10 | 150 | 18 | 10 NOT_EVALUATED |
| **Total único** | **20** | **730** | **60** | |

**Importante:** las 730 observaciones y los 60 snapshots corresponden a las evidencias de los 20 casos únicos; **no** se duplican al ejecutar dos proveedores sobre las mismas entradas.

## Resultados comparativos

| Experimento / proveedor | Decisiones propuestas | Decisiones efectivas | Sobrescrituras |
|---|---|---|---:|
| EXP-001 / Local | 8 Maintain; 2 Insufficient Evidence | 8 Maintain; 2 Insufficient Evidence | 0 |
| EXP-001 / Bedrock | 10 Maintain | 10 Maintain | 0 |
| EXP-002 / Local | 3 Maintain; 1 Optimize; 6 Insufficient Evidence | 10 Insufficient Evidence | 4 |
| EXP-002 / Bedrock | 8 Maintain; 2 Insufficient Evidence | 10 Insufficient Evidence | 8 |

La concordancia entre decisiones propuestas es **8/10 (80 %) en EXP-001** y **5/10 (50 %) en EXP-002**. La concordancia de decisiones efectivas es **8/10 (80 %) en EXP-001** y **10/10 (100 %) en EXP-002**. La concordancia efectiva perfecta de EXP-002 es consecuencia de los guardrails, no prueba de equivalencia entre modelos.

### Hallazgos por experimento

**EXP-001.** Las diez ejecuciones tienen `sla_status=PASS`. Bedrock propone `Maintain` en todas; el modelo local indica `Insufficient Evidence` para LB-01 en ambas campañas. No se activaron sobrescrituras. La divergencia de LB-01 debe presentarse como desacuerdo entre proveedores y no como error automáticamente atribuible a uno de ellos.

**EXP-002.** Las diez ejecuciones están `COMPLETED`, pero el SLA oficial figura `NOT_EVALUATED`. El guardrail convierte las doce propuestas accionables de ambos modelos en `Insufficient Evidence`. El p95 crece de ~10 ms en DB-01 a ~1.400–1.500 ms en DB-05, con tasa de errores normalizada igual a 0 en los diez casos. Esto muestra degradación de latencia a mayor carga, pero no permite afirmar formalmente PASS o FAIL del SLA sin umbrales y evaluación oficial.

### Caso de control: razonamiento de Bedrock frente a SLA

En el reporte de EXP-002 existen explicaciones generadas por Bedrock que mencionan que el SLA pasó, aunque el campo estructurado de entrada indica `NOT_EVALUATED`. Por tanto, el texto explicativo del modelo **no puede tratarse como evidencia validada**. La política de decisión actúa como barrera ante esa discrepancia. Se recomienda incorporar una verificación de consistencia entre las razones textuales y los campos estructurados antes de mostrar explicaciones al usuario final.

## Calidad, limitaciones y riesgos

- **SLA:** EXP-002 carece de evaluación oficial; no extrapolar de latencia y errores a un veredicto sin umbral definido.
- **Costo monetario:** `infrastructure_cost` y `monetary_cost` aparecen nulos; no se demostró ahorro en USD ni retorno financiero. El costo computacional proxy no equivale a facturación AWS.
- **Capacidad:** `capacity_headroom` no está disponible. No puede inferirse que una instancia sea redimensionable solo por CPU media baja.
- **Observabilidad:** las ventanas cortas contienen pocas muestras CloudWatch por recurso; snapshots Linux SSM son incompletos y CPU Linux puede no ser derivable.
- **Atribución:** para EXP-002 no debe confundirse carga de API, base de datos y generador Locust; no atribuir eficiencia por petición a una instancia sin rol confirmado.
- **Histórico:** algunos registros contienen `historical_telemetry.telemetry_quality=UNKNOWN` pese a existir `telemetry_contract` con mediciones. Se trata de estructuras distintas; debe explicitarse y corregirse el mapeo antes de usar la calidad histórica como condición de automatización.
- **Confianza:** Bedrock entrega `confidence_calibrated=false` y probabilidad/confianza nulas. No comparar directamente su certeza con las probabilidades del modelo local ni presentar porcentajes de confianza inventados.
- **Repetibilidad:** los dos proveedores reciben el mismo `run_id` y `evidence_sha256` por caso. La inferencia generativa puede variar en nuevas ejecuciones; los resultados documentados son una fotografía reproducible en términos de datos de entrada, no garantía de salida idéntica.
- **Operación:** el prototipo recomienda; no aplica automáticamente cambios de capacidad, escalamiento ni acciones correctivas en producción.

## Criterios de aceptación y veredicto

| Criterio | Veredicto |
|---|---|
| EXP-001 y EXP-002 ejecutados y evidenciados | CUMPLIDO |
| Procesamiento histórico de 20 casos | CUMPLIDO |
| Inferencia local y Bedrock | CUMPLIDO (40/40) |
| Trazabilidad por RUN_ID y hash de evidencia | CUMPLIDO en reportes |
| Guardrails y decisiones efectivas | CUMPLIDO |
| Comparación pareada entre proveedores | CUMPLIDO en este entregable |
| SLA evaluado para EXP-002 | NO CUMPLIDO |
| Ahorro monetario validado | NO DEMOSTRADO |
| Acciones automáticas de infraestructura | FUERA DEL ALCANCE MVP |
| Publicación y entrega al hackathon | PENDIENTE DE CONFIRMACIÓN EXTERNA |

**Conclusión:** el MVP está técnicamente integrado y cuenta con evidencias suficientes para documentar un cierre honesto de hackathon. Su valor demostrado es la ingestión histórica, la inferencia multiproveedor, la trazabilidad y la gobernanza de recomendaciones bajo evidencia incompleta. La evaluación integral de SLA y la optimización financiera verificable quedan como trabajo futuro.

## Reproducción y custodia

Los resultados originales son `reports/local_model/exp001_local.json`, `reports/local_model/exp002_local.json`, `reports/bedrock/exp001_bedrock.json`, `reports/bedrock/exp002_bedrock.json`. Los logs oficiales de Bedrock incluyen `OFFICIAL_RUNNER_VALIDATED`. Este paquete agrega `comparison_by_run.csv`, `comparison_summary.json` y `SOURCE_MANIFEST.sha256`. Los hashes del manifiesto identifican exactamente los archivos usados en el análisis.

Para reproducir la comparación **no se requiere AWS, credenciales, despliegue ni reinstalación de dependencias**: basta con los cuatro JSON y el script `compare_reports.py` incluido en el paquete.

## Trabajo futuro (no atribuir al MVP)

1. Contrato formal de SLA por escenario, con umbrales p95, error rate y disponibilidad.
2. Enriquecimiento de capacidad por rol y tipo de instancia, medición de headroom y CPU credits.
3. Datos de costos de AWS y validación del ahorro potencial contra alternativas reales.
4. Mejorar frecuencia de observabilidad y cobertura PRE/RUN/POST, respetando la granularidad de CloudWatch.
5. Validar consistencia factual de justificaciones generadas y calibrar incertidumbre.
6. Nuevas campañas de estrés sostenido, saturación, recuperación y pruebas multi-servicio, sin afirmar que se ejecutaron en esta entrega.
