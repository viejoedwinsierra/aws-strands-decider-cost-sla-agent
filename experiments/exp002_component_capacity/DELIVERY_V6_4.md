# EXP-002 V6.4 — integración local y preparación AWS

## Resultado comprobado
- Se inspeccionó el ZIP recibido, sin desplegar infraestructura ni consultar AWS.
- Se conservó EXP-001 y la evidencia histórica incluida.
- YAML V6.4 valida métodos, rutas, pesos, payloads, timeouts y SLA; mantiene YAML legado.
- Orquestador transmite política SLA y contrato HTTP por variables de entorno.
- Runner codifica el contrato y lo entrega a Locust mediante SSM sin editar manualmente el servidor.
- Locust soporta métodos GET/POST/PUT/PATCH/DELETE, identificadores propios por usuario, pesos y rutas dinámicas.
- Suite EXP-002: 19 pruebas exitosas; dry-run DB-SMOKE/DB-CRUD exitoso.

## Limitaciones pendientes para aceptación final
- No se realizó una prueba PostgreSQL real ni integración remota con EC2/SSM/S3.
- El CRUD FastAPI existente no incorpora propietario/namespace de campaña en base de datos. Locust restringe DELETE a IDs propios, pero otros clientes podrían borrar cualquier ID conocido: no afirmar aislamiento fuerte.
- Falta prueba funcional con PostgreSQL de los cinco métodos y respuestas de error.
- La telemetría actual del runner toma snapshots Linux y métricas CloudWatch de ambas EC2; no se ha demostrado cobertura continua de PRE/RUN/POST ni disponibilidad temporal de cada datapoint.
- La evidencia S3 del runner verifica manifiesto descargado, pero no hace HEAD/checksum independiente por objeto.
- El estado SLA FAIL se registra, pero debe confirmarse la semántica de salida y clasificación de campañas ante incumplimientos.
- No se comprobó identidad de cuenta AWS ni estado de instancias. No desplegar sin preflight.

## Comandos de validación local (WSL, desde raíz)
```bash
python3 -m compileall -q experiments/exp002_component_capacity
python3 -m unittest discover -s experiments/exp002_component_capacity/tests -v
python3 experiments/exp002_component_capacity/infrastructure_test/python/sequence_runner.py --config experiments/exp002_component_capacity/config/test_sequence_crud_v64.yml --dry-run
```

## Preflight AWS, lectura únicamente
```bash
: "${AWS_PROFILE:?set AWS_PROFILE explicitly}"
: "${AWS_REGION:?set AWS_REGION explicitly}"
aws --profile "$AWS_PROFILE" --region "$AWS_REGION" sts get-caller-identity
aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,State.Name,Tags[?Key==`Experiment`].Value|[0]]' --output table
aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ssm describe-instance-information --output table
```

**No ejecutar campañas hasta validar scripts oficiales, instancia/rol, bucket y permisos.** La configuración V6.4 se transmite desde `sequence_runner.py` al runner oficial; el despliegue del locustfile actualizado debe efectuarse con el mecanismo oficial antes de ejecutar. La campaña AWS todavía no está certificada.
