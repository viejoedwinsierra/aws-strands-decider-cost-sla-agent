#!/usr/bin/env python3
"""Install cron host collector on tagged campaign EC2 and retrieve bounded window via SSM."""
import argparse
import base64
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
REMOTE_SCRIPT = '/usr/local/libexec/exp001-linux-snapshot.py'
CRON_FILE = '/etc/cron.d/exp001-linux-monitor'

def aws(profile, region, *args):
    p = subprocess.run(['aws','--profile',profile,'--region',region,*args,'--output','json','--no-cli-pager'],capture_output=True,text=True)
    if p.returncode:
        raise RuntimeError(f'AWS {args[0]} {args[1]}: {p.stderr.strip()}')
    return json.loads(p.stdout) if p.stdout.strip() else {}

def remote(profile,region,instance,commands):
    result = aws(profile,region,'ssm','send-command','--instance-ids',instance,'--document-name','AWS-RunShellScript',
                 '--parameters',json.dumps({'commands':commands}),'--timeout-seconds','180')
    cid = result['Command']['CommandId']
    for _ in range(65):
        time.sleep(2)
        try:
            inv = aws(profile,region,'ssm','get-command-invocation','--command-id',cid,'--instance-id',instance)
        except RuntimeError as exc:
            if 'InvocationDoesNotExist' in str(exc):
                continue
            raise
        status = inv['Status']
        if status in ('Success','Failed','Cancelled','TimedOut','Cancelling'):
            if status != 'Success' or inv.get('ResponseCode') != 0:
                raise RuntimeError(f'SSM {instance} {cid} {status}: {inv.get("StandardErrorContent", "")}')
            return inv.get('StandardOutputContent','').strip()
    raise RuntimeError(f'SSM timeout {instance} {cid}')

def install(profile,region,ids):
    encoded = base64.b64encode((ROOT/'linux_snapshot.py').read_bytes()).decode()
    commands = [
        'set -eu',
        'dnf install -y cronie',
        'mkdir -p /usr/local/libexec /var/lib/exp001-monitor /etc/cron.d',
        f"printf '%s' '{encoded}' | base64 -d > {REMOTE_SCRIPT}",
        f'chmod 755 {REMOTE_SCRIPT}',
        f"printf '%s\\n' 'SHELL=/bin/sh' 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' '* * * * * root /usr/bin/python3 {REMOTE_SCRIPT} >> /var/log/exp001-monitor-cron.log 2>&1' > {CRON_FILE}",
        f'chmod 644 {CRON_FILE}',
        'systemctl enable --now crond',
        f'/usr/bin/python3 {REMOTE_SCRIPT}',
        f'test -s /var/lib/exp001-monitor/host_metrics.jsonl && systemctl is-active crond && cat {CRON_FILE}',
    ]
    for iid in ids:
        output = remote(profile,region,iid,commands)
        if 'active' not in output or REMOTE_SCRIPT not in output:
            raise RuntimeError(f'Cron validation failed for {iid}: {output}')
        print(f'LINUX_MONITOR_INSTALLED: {iid} cron=every-minute',flush=True)

def retrieve(profile,region,ids,start,end,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    start_dt = dt.datetime.fromisoformat(start.replace('Z','+00:00'))
    end_dt = dt.datetime.fromisoformat(end.replace('Z','+00:00'))
    report={}
    for iid in ids:
        # A bounded 16 KiB compressed payload fits SSM stdout (24 KiB limit).
        code = '''import base64,datetime,gzip,json,pathlib
start=datetime.datetime.fromisoformat(START.replace('Z','+00:00'))
end=datetime.datetime.fromisoformat(END.replace('Z','+00:00'))
p=pathlib.Path('/var/lib/exp001-monitor/host_metrics.jsonl')
records=[]
for line in p.read_text().splitlines():
 try:
  obj=json.loads(line); ts=datetime.datetime.fromisoformat(obj['timestamp_utc'])
  if start<=ts<=end: records.append(obj)
 except (ValueError,KeyError): continue
payload=gzip.compress(('\\n'.join(json.dumps(x,sort_keys=True) for x in records)+'\\n').encode())
if len(payload)>16000: raise RuntimeError('SSM payload too large; use paginated retrieval')
print(base64.b64encode(payload).decode())'''
        code=code.replace('START',repr(start)).replace('END',repr(end))
        encoded=base64.b64encode(code.encode()).decode()
        response=remote(profile,region,iid,[f"printf '%s' '{encoded}' | base64 -d | /usr/bin/python3"])
        payload=gzip.decompress(base64.b64decode(response,validate=True))
        rows=[json.loads(line) for line in payload.splitlines() if line.strip()]
        if not rows:
            raise RuntimeError(f'No Linux snapshots in campaign window for {iid}')
        target=outdir/f'{iid}.jsonl'
        target.write_bytes(payload)
        report[iid]={'samples':len(rows),'sha256':hashlib.sha256(payload).hexdigest(),'first_utc':rows[0]['timestamp_utc'],'last_utc':rows[-1]['timestamp_utc']}
        print(f'LINUX_MONITOR_RETRIEVED: {iid} samples={len(rows)}',flush=True)
    (outdir/'linux_monitor_report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def upload(profile,region,bucket,campaign,outdir,ids):
    prefix=f'experiments/exp001_capacity/results/campaigns/{campaign}/linux'
    for name in [*(f'{i}.jsonl' for i in ids),'linux_monitor_report.json']:
        path=outdir/name
        key=f's3://{bucket}/{prefix}/{name}'
        subprocess.run(['aws','--profile',profile,'--region',region,'s3','cp',str(path),key,'--sse','AES256','--no-progress'],check=True)
        result=subprocess.run(['aws','--profile',profile,'--region',region,'s3','cp',key,'-','--no-progress'],check=True,capture_output=True)
        if hashlib.sha256(result.stdout).digest()!=hashlib.sha256(path.read_bytes()).digest():
            raise RuntimeError(f'S3 SHA256 mismatch: {name}')
        print(f'LINUX_MONITOR_S3_VERIFIED: {name}',flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['install','collect'])
    for key in ('profile','region','http-id','locust-id'):
        p.add_argument('--'+key,required=True)
    for key in ('campaign-id','start','end','bucket','output-dir'):
        p.add_argument('--'+key)
    a=p.parse_args()
    ids=[a.http_id,a.locust_id]
    if len(set(ids))!=2: p.error('Expected two distinct EC2 instances')
    if a.action=='install': install(a.profile,a.region,ids)
    else:
        if not all([a.campaign_id,a.start,a.end,a.bucket,a.output_dir]): p.error('collect requires campaign fields')
        outdir=Path(a.output_dir)
        retrieve(a.profile,a.region,ids,a.start,a.end,outdir)
        upload(a.profile,a.region,a.bucket,a.campaign_id,outdir,ids)
        print('LINUX_MONITOR_EVIDENCE_VERIFIED',flush=True)

if __name__=='__main__':
    try: main()
    except (OSError,RuntimeError,subprocess.CalledProcessError,ValueError,KeyError) as exc:
        print(f'LINUX_MONITOR_FAILED: {exc}',file=sys.stderr)
        sys.exit(1)
