#!/usr/bin/env python3
"""One-shot Linux host snapshot; invoked once a minute by cron."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import socket

ROOT = Path('/var/lib/exp001-monitor')
ROOT.mkdir(parents=True, exist_ok=True)

def proc_stat():
    line = Path('/proc/stat').read_text().splitlines()[0].split()
    vals = [int(v) for v in line[1:]]
    return {'cpu_total_jiffies': sum(vals), 'cpu_idle_jiffies': vals[3] + (vals[4] if len(vals)>4 else 0)}

def mem():
    out = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k, _, v = line.partition(':')
        if k in ('MemTotal','MemAvailable','SwapTotal','SwapFree'):
            out[k + '_kb'] = int(v.strip().split()[0])
    return out

def snapshot():
    st = os.statvfs('/')
    return {'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'hostname': socket.gethostname(), 'schema_version': '1.0',
            'cpu': proc_stat(), 'memory': mem(),
            'disk_root': {'total_bytes': st.f_blocks*st.f_frsize, 'free_bytes': st.f_bavail*st.f_frsize},
            'load_average': list(os.getloadavg())}

def main():
    with (ROOT/'snapshot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (ROOT/'host_metrics.jsonl').open('a', encoding='utf-8') as out:
            out.write(json.dumps(snapshot(), sort_keys=True)+'\n')

if __name__ == '__main__':
    main()
