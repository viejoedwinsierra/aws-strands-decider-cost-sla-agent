#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/provision.sh."""
import os
from pathlib import Path
p = Path(os.environ['CONFIG_FILE'])
values = {k: os.environ[k] for k in ('AWS_PROFILE','AWS_REGION','PROJECT_TAG','EXPERIMENT_ID')}
role = os.environ['INSTANCE_ROLE']
instance_id = os.environ['INSTANCE_ID']
if role == 'http-server':
    values['INSTANCE_ID'] = instance_id
    values['HTTP_INSTANCE_ID'] = instance_id
elif role == 'load-generator':
    values['LOCUST_INSTANCE_ID'] = instance_id
elif role == 'decider-2b':
    values['DECIDER_INSTANCE_ID'] = instance_id
else:
    raise SystemExit(f'Rol no soportado: {role}')
lines = p.read_text().splitlines() if p.exists() else []
seen = set()
out = []
for line in lines:
    key = line.split('=', 1)[0].strip() if '=' in line else None
    if key in values:
        out.append(f'{key}={values[key]}')
        seen.add(key)
    else:
        out.append(line)
for key, value in values.items():
    if key not in seen:
        out.append(f'{key}={value}')
tmp = p.with_suffix('.tmp')
tmp.write_text('\n'.join(out) + '\n')
tmp.replace(p)
print(f'Configuracion actualizada: {p}', file=__import__('sys').stderr)
