# 06 — Arquitectura, observabilidad y evolución del ciclo de vida

## Resultado demostrado

InfraVita V2 integra experimentos de carga HTTP (EXP-001) y API/BD (EXP-002), métricas de CloudWatch, snapshots Linux vía SSM, evidencias identificadas por RUN_ID y SHA-256, inferencia con Strands Decider local y Amazon Bedrock Nova Micro, y guardrails deterministas. El prototipo **recomienda**, no ejecuta automáticamente cambios en AWS.

## Limitación estadística central

Las campañas de 60 y 120 segundos fueron demasiado cortas para muestrear suficientemente dinámicas de carga, variabilidad temporal, saturación sostenida, colas, créditos de CPU, recuperación y costos. El número de muestras CloudWatch por ventana es limitado. EXP-002 tiene SLA `NOT_EVALUATED`. No es válido inferir ahorro monetario, SLA productivo ni capacidad futura de estos resultados.

## Arquitectura objetivo (futuro, no demostrado en MVP)

**Ciclo de vida integrado:** aprovisionamiento → despliegue → operación → monitoreo → detección de anomalías → decisión (mantener/optimizar/escalar/evolucionar) → recuperación/degradación → retiro.

**Contrato de observabilidad:** combinar métricas administradas de nube (CloudWatch), métricas propias de sistemas operativos y aplicaciones, inventario de recursos por etiquetas, ventanas temporales, topología y dependencias, calidad y granularidad de datos, trazabilidad por ejecución y costos imputables por servicio.

**Costos:** separar costo de cómputo/almacenamiento/red, costo de observabilidad (ingesta, retención, consultas, métricas personalizadas), costo de operación y riesgo de SLA. No confundir índices de eficiencia con facturación monetaria.

**Evolución metodológica:** extender campañas, replicar a distintas horas y días, instrumentar PRE/RUN/POST, registrar recursos por rol, usar distribuciones e intervalos de incertidumbre, calibrar contra datos reales de facturación, evaluar umbrales SLA explícitos y analizar decisiones a lo largo del tiempo.

## Declaración de alcance

**Validado:** cadena experimental, almacenamiento y recuperación histórica, 40 inferencias sobre 20 evidencias únicas, comparación y guardrails. **Pendiente:** evaluación SLA EXP-002, modelos de costo monetario, validación estadística longitudinal, gestión integral automatizada del ciclo de vida y publicación oficial del hackathon.
