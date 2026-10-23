# Plan de validación

| Validación | Comando o procedimiento | ¿Infiere? | ¿Usa AWS? |
|---|---|---|---|
| Dependencias | `bash scripts/start_agent.sh --check --offline` | No | No |
| JSON | `python -m json.tool RUTA.json >/dev/null` | No | No |
| Integridad | `sha256sum RUTA.json` | No | No |
| Comparación | `python docs/validation/compare_existing_reports.py` | No | No |
| EXP-001 configuración | `bash experiments/exp001_capacity/infrastructure_test/run.sh --dry-run` | No | No, según runner |
| EXP-002 configuración | `bash experiments/exp002_component_capacity/infrastructure_test/run.sh --dry-run` | No | No, según runner |
| Campaña real | `run.sh --execute` (EXP-002) | No modelo | **Sí; no ejecutar en cierre offline** |

La ejecución de `--dry-run` depende de la presencia de archivos de configuración local. EXP-001 carga `experiment.env` antes de evaluar `--dry-run`; si falta, el comando fallará aunque no use AWS. No usar `--execute` ni desplegar infraestructura durante el cierre.

Verificar también `git diff --check`, `git status --short`, que no se agreguen `.env` ni credenciales y que no se mezclen los perfiles AWS Academy y Bedrock.
