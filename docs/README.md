# InfraVita V2 — Documentation index

[← Executive README](../README.md) · [Deployment](operations/INFRASTRUCTURE_DEPLOYMENT.md) · [Experiment execution](operations/EXPERIMENT_EXECUTION.md) · [Offline audit](operations/OFFLINE_AUDIT.md)

![System architecture](images/architecture.svg)

## Start here

| Reader's question | Chapter |
|---|---|
| What is InfraVita, and why does an idle service still have a cost? | [Executive README](../README.md), [Architecture and roadmap](architecture/VISION_Y_EVOLUCION.md) |
| How do I deploy AWS resources? | [Infrastructure deployment](operations/INFRASTRUCTURE_DEPLOYMENT.md) |
| How do I run EXP-001 and EXP-002? | [Experiment execution](operations/EXPERIMENT_EXECUTION.md) |
| How do I validate existing results without AWS or inference? | [Offline audit](operations/OFFLINE_AUDIT.md), [Validation catalogue](validation/CATALOGO_SCRIPTS.md) |
| What happened in the two experiments? | [Results](experiments/RESULTADOS_Y_ESTADISTICAS.md), [Evidence matrix](experiments/MATRIZ_EVIDENCIAS.md) |
| What do CPU and memory measurements actually show? | [Resource utilization](experiments/RESOURCE_UTILIZATION.md) |
| How did local and Bedrock recommendations differ? | [Model comparison](models/COMPARACION_LOCAL_BEDROCK.md), [Traceability](models/TRAZABILIDAD_SIN_INFERENCIA.md) |
| What can we responsibly claim for the hackathon? | [Final report](hackathon/INFORME_FINAL.md) |
| Which scripts and flags exist? | [Command reference](operations/COMANDOS_PRINCIPALES.md), [Script catalogue](validation/CATALOGO_SCRIPTS.md) |
| How were the images produced? | [Charts and provenance](images/README.md) |
| How did the earlier implementation evolve? | [Delivery 9 baseline](delivery9/00_baseline.md), [architecture](delivery9/01_architecture.md), [execution log](delivery9/execution_log.md) |
| How does Bedrock authentication work? | [Bedrock execution](BEDROCK_EXECUTION.md) |

## Evidence hierarchy

1. **Observed:** experiment telemetry and run summaries, paired by RUN_ID and evidence SHA-256.
2. **Proposed:** provider-generated raw recommendation and rationale.
3. **Effective:** computational policy output after SLA/evidence checks.
4. **Not established:** verified monetary savings, EXP-002 SLA PASS/FAIL, sustained saturation, long-term reliability.

**Historical source preservation:** `SOURCE_DOCUMENTATION_ARCHIVE.zip` at the package root contains the exact uploaded documentation before English editorial changes. All active Markdown pages in `docs/` are in English. The archive is reference material, not a second authoritative documentation tree.
