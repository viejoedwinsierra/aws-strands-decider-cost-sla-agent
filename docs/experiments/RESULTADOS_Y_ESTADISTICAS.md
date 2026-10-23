# 01 — Estadísticas y resultados experimentales

**Corte: 23 octubre 2026.** Fuente: cuatro reportes JSON y comparación pareada por `run_id`. Estadísticas descriptivas de ejecuciones cortas; no son inferencias poblacionales.

## Cobertura y calidad

| Experimento | Casos | Campañas | CloudWatch | Linux SSM | SLA |
|---|---:|---:|---:|---:|---|
| EXP-001 | 10 | 2 | 580 | 42 | 10 PASS |
| EXP-002 | 10 | 2 | 150 | 18 | 10 NOT_EVALUATED |
| **Total** | **20** | **4** | **730** | **60** | — |

Las 40 inferencias (20 local, 20 Bedrock) reutilizan las **mismas 20 evidencias**, por lo que las muestras de observabilidad no se multiplican por dos. Campañas nominales de 60 y 120 segundos, con cinco niveles de usuarios (10, 100, 200, 300 y 500) por experimento.

## Métricas de carga observadas

| Experimento | p95 mínimo (ms) | p95 mediano (ms) | p95 máximo (ms) | RPS mínimo | RPS máximo | Solicitudes sumadas* | Casos con error_rate > 0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| EXP-001 | 4.00 | 11.50 | 19.00 | 9.78 | 384.23 | 150409 | 1 |
| EXP-002 | 10.00 | 270.00 | 1500.00 | 15.84 | 241.10 | 152844 | 0 |

*Suma descriptiva de los conteos reportados por escenario; no debe interpretarse como un único test continuo. p95 mediano = mediana de los p95 por ejecución, **no** p95 global de solicitudes.

## Detalle por escenario y campaña

| Exp. | Escenario | Campaña | Estado | SLA | p95 (ms) | RPS | Error rate | CloudWatch | Linux SSM |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| EXP-001 | LB-01 | exp001_20261023T200309125677014Z | COMPLETED | PASS | 5.00 | 9.78 | 0.00 | 82 | 6 |
| EXP-001 | LB-02 | exp001_20261023T200309125677014Z | COMPLETED | PASS | 7.00 | 86.22 | 0.00 | 60 | 4 |
| EXP-001 | LB-03 | exp001_20261023T200309125677014Z | COMPLETED | PASS | 9.00 | 165.03 | 0.00 | 66 | 4 |
| EXP-001 | LB-04 | exp001_20261023T200309125677014Z | FAILED | PASS | 12.00 | 255.35 | 0.00 | 82 | 6 |
| EXP-001 | LB-05 | exp001_20261023T200309125677014Z | COMPLETED | PASS | 19.00 | 384.23 | 0.00 | 82 | 6 |
| EXP-001 | LB-01 | exp001_20261023T202530766985857Z | COMPLETED | PASS | 4.00 | 9.78 | 0.00 | 44 | 4 |
| EXP-001 | LB-02 | exp001_20261023T202530766985857Z | COMPLETED | PASS | 14.00 | 72.87 | 0.00 | 38 | 2 |
| EXP-001 | LB-03 | exp001_20261023T202530766985857Z | COMPLETED | PASS | 11.00 | 133.45 | 0.00 | 22 | 2 |
| EXP-001 | LB-04 | exp001_20261023T202530766985857Z | COMPLETED | PASS | 14.00 | 223.22 | 0.00 | 60 | 4 |
| EXP-001 | LB-05 | exp001_20261023T202530766985857Z | COMPLETED | PASS | 19.00 | 288.28 | 0.00 | 44 | 4 |
| EXP-002 | DB-01 | exp002_campaign_20261023T200424Z | COMPLETED | NOT_EVALUATED | 10.00 | 15.84 | 0.00 | 12 | 1 |
| EXP-002 | DB-02 | exp002_campaign_20261023T200424Z | COMPLETED | NOT_EVALUATED | 37.00 | 145.08 | 0.00 | 12 | 2 |
| EXP-002 | DB-03 | exp002_campaign_20261023T200424Z | COMPLETED | NOT_EVALUATED | 280.00 | 193.23 | 0.00 | 12 | 2 |
| EXP-002 | DB-04 | exp002_campaign_20261023T200424Z | COMPLETED | NOT_EVALUATED | 630.00 | 230.25 | 0.00 | 12 | 2 |
| EXP-002 | DB-05 | exp002_campaign_20261023T200424Z | COMPLETED | NOT_EVALUATED | 1400.00 | 226.92 | 0.00 | 12 | 2 |
| EXP-002 | DB-01 | exp002_campaign_20261023T202944Z | COMPLETED | NOT_EVALUATED | 10.00 | 16.81 | 0.00 | 18 | 2 |
| EXP-002 | DB-02 | exp002_campaign_20261023T202944Z | COMPLETED | NOT_EVALUATED | 33.00 | 157.55 | 0.00 | 18 | 2 |
| EXP-002 | DB-03 | exp002_campaign_20261023T202944Z | COMPLETED | NOT_EVALUATED | 260.00 | 224.96 | 0.00 | 18 | 1 |
| EXP-002 | DB-04 | exp002_campaign_20261023T202944Z | COMPLETED | NOT_EVALUATED | 700.00 | 238.65 | 0.00 | 18 | 2 |
| EXP-002 | DB-05 | exp002_campaign_20261023T202944Z | COMPLETED | NOT_EVALUATED | 1500.00 | 241.10 | 0.00 | 18 | 2 |

## Decisiones y concordancia

| Experimento | Local: propuestas | Bedrock: propuestas | Acuerdo bruto | Acuerdo efectivo | Intervenciones local / Bedrock |
|---|---|---|---:|---:|---:|
| EXP-001 | 2 Insufficient Evidence, 8 Maintain | 10 Maintain | 8/10 | 8/10 | 0 / 0 |
| EXP-002 | 6 Insufficient Evidence, 3 Maintain, 1 Optimize | 2 Insufficient Evidence, 8 Maintain | 5/10 | 10/10 | 4 / 8 |

## Discrepancias identificables

| RUN_ID | Local propuesto | Bedrock propuesto | Local efectivo | Bedrock efectivo |
|---|---|---|---|---|
| exp001_20261023T200309125677014Z_LB01_A01 | Insufficient Evidence | Maintain | Insufficient Evidence | Maintain |
| exp001_20261023T202530766985857Z_LB01_A01 | Insufficient Evidence | Maintain | Insufficient Evidence | Maintain |
| exp002_campaign_20261023T200424Z_DB-01 | Insufficient Evidence | Maintain | Insufficient Evidence | Insufficient Evidence |
| exp002_campaign_20261023T200424Z_DB-02 | Insufficient Evidence | Maintain | Insufficient Evidence | Insufficient Evidence |
| exp002_campaign_20261023T200424Z_DB-03 | Insufficient Evidence | Maintain | Insufficient Evidence | Insufficient Evidence |
| exp002_campaign_20261023T202944Z_DB-02 | Insufficient Evidence | Maintain | Insufficient Evidence | Insufficient Evidence |
| exp002_campaign_20261023T202944Z_DB-03 | Optimize | Maintain | Insufficient Evidence | Insufficient Evidence |

## Límites del muestreo

- Los intervalos 60/120 s no caracterizan ciclos horarios, diarios o estacionales; la granularidad CloudWatch limita el número de observaciones por ventana.
- En EXP-001 hay un `execution_status=FAILED` aunque su `sla_status=PASS`: estados de ejecución y SLA son dimensiones diferentes; revisar el manifiesto antes de usarlo como caso exitoso.
- EXP-002 carece de veredicto SLA; error_rate=0 no equivale a PASS.
- `capacity_headroom` e `infrastructure_cost` no están poblados en la comparación; no es posible declarar ahorro monetario o capacidad sobrante verificada.
- La coincidencia de modelos mide concordancia, no exactitud. La coincidencia efectiva de EXP-002 se debe al guardrail.

## Evolución metodológica

Esta fase demuestra una cadena reproducible de evidencia, normalización, decisión y gobernanza. Futuras campañas deberán ampliar duración, frecuencia de captura, ventanas PRE/RUN/POST, tipos de carga, correlación por componente, atribución de costos cloud y de monitoreo propio, evaluación de SLA y cobertura de las fases del ciclo de vida: aprovisionar, operar, escalar, recuperar, degradar, optimizar, evolucionar y retirar. **No atribuir estas capacidades futuras a los experimentos actuales.**
