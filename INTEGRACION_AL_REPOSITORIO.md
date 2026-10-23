# Integración segura al repositorio

Este ZIP es una **propuesta de integración**, basada en un snapshot previo del repositorio y en reportes históricos. No es un commit y no reemplaza automáticamente tu árbol de trabajo.

1. Extrae el ZIP en una carpeta temporal fuera del repositorio.
2. Revisa `README.md` propuesto y `docs/README.md`.
3. Copia `docs/` a la carpeta `docs/` del repositorio **fusionando directorios**, sin eliminar los archivos existentes; conserva especialmente `docs/BEDROCK_EXECUTION.md`.
4. Revisa el README original y sustituye `README.md` únicamente cuando confirmes que no se pierden enlaces o información que quieras preservar.
5. Copia `reports/comparison/` solo si esos CSV/JSON son publicables; no agregues archivos con datos sensibles.
6. Desde la raíz del repositorio ejecuta `python docs/validation/compare_existing_reports.py`, `git diff --check` y `git status --short`.
7. Inspecciona `git diff -- README.md docs/` y añade rutas específicas, no `git add .` ni `git add -A`.

Los documentos `docs/delivery9` incluidos corresponden al snapshot auditado, no sustituyen los archivos más recientes de tu rama.
