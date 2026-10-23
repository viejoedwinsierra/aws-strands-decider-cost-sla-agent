# Trazabilidad sin inferencia: opciones y validaciones

## Diferenciar modos

- `bash scripts/start_agent.sh --check --offline`: valida el entorno y dependencias, **no invoca modelos**.
- `bash scripts/setup_agent.sh --check --offline`: verifica dependencias; no instala ni infiere.
- `bash scripts/start_agent.sh --offline --infer ...`: **sí invoca inferencia**.
- `--local-root`: raíz de evidencias históricas; `--output`: ruta del JSON generado.
- `--provider local|bedrock`: proveedor en el flujo de inferencia verificado en las ejecuciones finales; requiere confirmar la interfaz de la versión instalada antes de automatizar.
- `--decision-policy computational-v1`: aplica política determinista; conservar también la decisión original del modelo.
- `--capacity-inventory`: inventario opcional de capacidad si la versión del integrador lo admite.
- `--install-missing`, `--install-all`: pueden instalar dependencias, **no usar en validación solo lectura**.

## Auditoría de reportes ya generados (sin modelos, AWS ni red)

```bash
python scripts/validate_historical_reports.py --help
python -m json.tool reports/bedrock/exp001_bedrock.json >/dev/null
python -m json.tool reports/bedrock/exp002_bedrock.json >/dev/null
sha256sum reports/bedrock/exp001_bedrock.json reports/bedrock/exp002_bedrock.json
```

El primer comando requiere que se copie el validador original del paquete documental a `scripts/`; la interfaz exacta se debe consultar mediante `--help` antes de utilizarlo. Los demás comandos son validaciones de sintaxis e integridad de archivos, **no** pruebas de calidad de decisión.

Para trazabilidad de cada decisión: registrar experimento, RUN_ID, hash de evidencia, versión de modelo, proveedor, política, decisión original, decisión efectiva, motivo de intervención, estado de SLA y disponibilidad de métricas. No atribuir probabilidades de confianza a Bedrock sin que el servicio las devuelva.
