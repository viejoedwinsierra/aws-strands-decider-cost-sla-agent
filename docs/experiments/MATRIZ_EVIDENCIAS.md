# Matriz de evidencias y procedencia

| Fuente | Evidencia | Propósito | Estado |
|---|---|---|---|
| EXP-001 | 10 ejecuciones / 2 campañas | HTTP, Locust, capacidad | Histórico procesado |
| EXP-002 | 10 ejecuciones / 2 campañas | FastAPI + PostgreSQL | Histórico procesado |
| CloudWatch | 730 observaciones reportadas | Infraestructura | Cobertura corta; no inferir tendencia temporal |
| Linux / SSM | 60 snapshots reportados | Sistema operativo | Complemento de CloudWatch |
| Local | 20 inferencias | Decisión propuesta | Completado |
| Bedrock | 20 inferencias | Decisión propuesta | Completado |
| `reports/comparison/comparison_by_run.csv` | Comparación por RUN_ID | Auditoría | Archivo incluido en paquete |

Los resultados son históricos; repetir inferencias **no** equivale a nuevas pruebas de carga. Las campañas de 60–120 s no prueban estacionalidad, costos de largo plazo ni ahorro logrado. En EXP-002 el SLA figura `NOT_EVALUATED`, no `PASS`.
