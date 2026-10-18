#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/deploy_locust.sh."""
import base64
import json
import os
from pathlib import Path
import sys

source = Path(os.environ["LOCUST_FILE"]).read_bytes()
payload = base64.b64encode(source).decode("ascii")
bucket = os.environ["EVIDENCE_BUCKET"]

cmd = f"""set -eu
mkdir -p /opt/exp001-locust
printf %s {payload} | base64 -d > /opt/exp001-locust/locustfile.py.next

python3 -m py_compile /opt/exp001-locust/locustfile.py.next

if ! cmp -s /opt/exp001-locust/locustfile.py.next /opt/exp001-locust/locustfile.py; then
  mv /opt/exp001-locust/locustfile.py.next /opt/exp001-locust/locustfile.py
  echo 'Locust workload updated'
else
  rm -f /opt/exp001-locust/locustfile.py.next
  echo 'Locust workload unchanged'
fi

if [ ! -x /opt/exp001-locust/venv311/bin/locust ]; then
  dnf install -y python3.11 python3.11-pip
  python3.11 -m venv /opt/exp001-locust/venv311
fi

mkdir -p /opt/exp001-locust/wheels311

aws s3 sync \
  s3://{bucket}/dependencies/locust/python311-linux-x86_64/ \
  /opt/exp001-locust/wheels311/

# Instalación estrictamente offline: no consulta PyPI.
# También permite corregir dependencias incompletas en ejecuciones anteriores.
/opt/exp001-locust/venv311/bin/python -m pip install \
  --no-index \
  --find-links=/opt/exp001-locust/wheels311 \
  'locust==2.46.7' \
  'typing-extensions>=4.6.0'

/opt/exp001-locust/venv311/bin/python -m pip check
/opt/exp001-locust/venv311/bin/locust --version
"""

Path(sys.argv[1]).write_text(json.dumps({"commands": [cmd]}))
