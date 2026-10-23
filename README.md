# InfraVita V2 — AWS Cost & SLA Decision Agent

**Una arquitectura experimental para decisiones trazables sobre capacidad, costos, SLA e integridad durante el ciclo de vida del software y la infraestructura.**

[Documentación completa](docs/README.md) · [Resultados](docs/experiments/RESULTADOS_Y_ESTADISTICAS.md) · [Comparación de modelos](docs/models/COMPARACION_LOCAL_BEDROCK.md) · [Cómo ejecutar](docs/operations/GUIA_EJECUCION.md)

![Flujo experimental](docs/images/architecture.svg)

## Resumen ejecutivo

InfraVita V2 integra pruebas reproducibles de servicios AWS, telemetría CloudWatch y Linux/SSM, evidencias históricas y dos proveedores de inferencia: Strands Decider local y Amazon Bedrock. Una política computacional separa la propuesta del modelo de la decisión efectiva, para evitar acciones que no estén justificadas por el estado de las evidencias.

## Resultados del hackathon

| Indicador | Resultado histórico |
|---|---:|
| Experimentos | 2 (HTTP/Locust; FastAPI/PostgreSQL) |
| Campañas / escenarios | 4 / 20 |
| Inferencias local / Bedrock | 20 / 20 |
| CloudWatch / snapshots Linux SSM | 730 / 60 |
| Acuerdo bruto local–Bedrock EXP-001 | 8/10 (80 %) |
| Acuerdo bruto local–Bedrock EXP-002 | 5/10 (50 %) |
| Acuerdo efectivo EXP-002 con guardrails | 10/10 (100 %) |

La concordancia entre modelos **no demuestra exactitud**. El acuerdo efectivo del EXP-002 responde a guardrails que mantuvieron decisiones conservadoras porque el SLA figuraba `NOT_EVALUATED`. Las campañas cortas (60–120 s) no bastan para inferir patrones estacionales ni calcular ahorros reales.

## Principio rector: integridad del sistema

La optimización no debe comprometer la disponibilidad, consistencia de datos, seguridad ni obligaciones de servicio. InfraVita prioriza **integridad de evidencias**, **trazabilidad por RUN_ID y hash**, **guardrails explícitos**, **separación de credenciales**, **reproducibilidad** y **capacidad de auditoría**. No ejecuta automáticamente una recomendación no validada.

## Conclusiones

El MVP demuestra integración funcional de los dos experimentos con dos proveedores y un mecanismo verificable de decisión controlada. **No demuestra todavía ahorro económico, predicción de saturación en producción ni cumplimiento longitudinal de SLA**. El valor de esta entrega es crear una base técnica medible, extensible y auditable.

## Próximos avances y aplicaciones

1. Campañas más largas y replicadas para estudiar demanda, latencia, colas y degradación sostenida.
2. Costeo end-to-end: cómputo, almacenamiento, transferencia, observabilidad, operación y evolución.
3. Decisiones de capacidad, consolidación, escalamiento, modernización y retiro basadas en costo–riesgo–SLA.
4. Observabilidad de aplicaciones empresariales, plataformas de datos, sistemas regulatorios y arquitecturas multi-cloud.
5. Gobierno de datos, versiones de modelos, experimentos controlados y evaluación independiente de recomendaciones.

## Navegación

Empieza en el [índice técnico](docs/README.md). Consulta la [matriz de evidencias](docs/experiments/MATRIZ_EVIDENCIAS.md), la [guía de operación](docs/operations/GUIA_EJECUCION.md) y los [controles sin inferencia](docs/models/TRAZABILIDAD_SIN_INFERENCIA.md).

> La infraestructura experimental ya fue retirada. La documentación de cierre usa evidencias históricas; no se necesita desplegar recursos para revisar los resultados.
