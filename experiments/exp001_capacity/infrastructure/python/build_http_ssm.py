#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/deploy_http.sh."""
import base64, json, os, pathlib, sys
source = pathlib.Path(os.environ['SERVER_FILE']).read_bytes()
payload = base64.b64encode(source).decode('ascii')
service = """[Unit]
Description=EXP-001 HTTP Server
After=network.target
[Service]
Type=simple
User=root
WorkingDirectory=/opt/exp001-http
Environment=HTTP_HOST=0.0.0.0
Environment=HTTP_PORT=8080
ExecStart=/usr/bin/python3 /opt/exp001-http/server.py
Restart=on-failure
[Install]
WantedBy=multi-user.target
"""
svc = base64.b64encode(service.encode()).decode('ascii')
# Remote script is idempotent: check installed files + active service + health.
cmd = f"""set -eu
mkdir -p /opt/exp001-http
printf %s {payload} | base64 -d > /opt/exp001-http/server.py.next
printf %s {svc} | base64 -d > /etc/systemd/system/exp001-http.service.next
python3 -m py_compile /opt/exp001-http/server.py.next
changed=0
if ! cmp -s /opt/exp001-http/server.py.next /opt/exp001-http/server.py; then
  mv /opt/exp001-http/server.py.next /opt/exp001-http/server.py
  changed=1
else
  rm -f /opt/exp001-http/server.py.next
fi
if ! cmp -s /etc/systemd/system/exp001-http.service.next /etc/systemd/system/exp001-http.service; then
  mv /etc/systemd/system/exp001-http.service.next /etc/systemd/system/exp001-http.service
  systemctl daemon-reload
  changed=1
else
  rm -f /etc/systemd/system/exp001-http.service.next
fi
if [ "$changed" -eq 1 ] || ! systemctl is-active --quiet exp001-http; then
  systemctl enable exp001-http >/dev/null
  systemctl restart exp001-http
  echo 'HTTP deployment applied'
else
  echo 'HTTP files unchanged; service already running'
fi
ok=0
for i in $(seq 1 20); do
  if curl -fsS --max-time 2 http://127.0.0.1:8080/health; then ok=1; break; fi
  sleep 1
done
[ "$ok" -eq 1 ] || {{ journalctl -u exp001-http -n 30 --no-pager; exit 1; }}
"""
pathlib.Path(sys.argv[1]).write_text(json.dumps({'commands': [cmd]}))
