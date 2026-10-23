# 02 — Comparación entre Strands Decider local y Amazon Bedrock

## Identidad y trazabilidad

- Proveedor local: Strands Decider 2B v21, ejecución en el entorno Python existente.
- Proveedor Bedrock: Amazon Nova Micro, `us.amazon.nova-micro-v1:0`, región `us-east-2`.
- Política posterior: `computational-v1` (guardrail). Ambos reciben el mismo `run_id` y `evidence_sha256` por caso.
- **No son el mismo modelo** y no existe una referencia de verdad independiente que permita proclamar cuál es superior.

## Resultados verificables

| Experimento | Acuerdo bruto | Acuerdo efectivo | Guardrail local | Guardrail Bedrock |
|---|---:|---:|---:|---:|
| EXP-001 | 8/10 (80 %) | 8/10 (80 %) | 0 | 0 |
| EXP-002 | 5/10 (50 %) | 10/10 (100 %) | 4 | 8 |

En EXP-001, el modelo local propone `Insufficient Evidence` en LB-01 de ambas campañas, mientras Bedrock propone `Maintain`; en los demás casos ambos proponen `Maintain`.

En EXP-002, las 10 decisiones efectivas de ambos proveedores son `Insufficient Evidence` debido a `sla_status=NOT_EVALUATED`. Los guardrails rechazan las propuestas accionables (local 4; Bedrock 8). El acuerdo efectivo del 100 % **no demuestra equivalencia semántica de los modelos**.

## Interpretación y riesgos

1. El texto explicativo de Bedrock puede describir un SLA como aprobado aunque el campo estructurado sea `NOT_EVALUATED`; la explicación generativa requiere verificación factual.
2. Bedrock no aporta probabilidades calibradas equivalentes a las del modelo local (`confidence_calibrated=false`); no inventar porcentajes de confianza.
3. La ejecución generativa puede variar entre repeticiones; este corte documenta las salidas capturadas, no estabilidad longitudinal de modelos.
4. La política conservadora es un mecanismo de gobernanza, no una medición de precisión del modelo.
5. No hubo cambios automáticos de capacidad ni ahorro económico verificado.

## Archivos para auditoría

- `comparison_by_run.csv`: decisiones brutas y efectivas por RUN_ID, hashes, SLA, métricas.
- `comparison_summary.json`: consolidado calculado y hashes de fuentes.
- `sources/*.json`: cuatro reportes originales.
- `compare_reports.py`: recomputación sin acceso a AWS.

La tabla exhaustiva de discrepancias está en `01_ESTADISTICAS_Y_PRUEBAS.md`.
