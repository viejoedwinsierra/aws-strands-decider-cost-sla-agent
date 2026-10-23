#!/usr/bin/env python3
"""EXP-002 AWS run orchestration. No resources created; explicit run only."""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = os.environ.get('RUN_ID') or 'exp002_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
if not re.fullmatch(r'[A-Za-z0-9_-]+', RUN_ID):
    raise SystemExit('Invalid RUN_ID')
BUCKET = os.environ.get('EVIDENCE_BUCKET', '')
WORKLOAD = os.environ.get('WORKLOAD_INSTANCE_ID', '')
LOCUST = os.environ.get('LOCUST_INSTANCE_ID', '')
BUNDLE = os.environ.get('LOCUST_BUNDLE_HASH', '')
USERS = int(os.environ.get('USERS', '5'))
SPAWN = float(os.environ.get('SPAWN_RATE', '1'))
DURATION = os.environ.get('DURATION', '60s')
if not (BUCKET and WORKLOAD and LOCUST and re.fullmatch('[0-9a-f]{64}', BUNDLE)):
    raise SystemExit('Missing EVIDENCE_BUCKET, EC2 IDs, or LOCUST_BUNDLE_HASH')
if USERS <= 0 or SPAWN <= 0 or not re.fullmatch(r'[1-9][0-9]*s', DURATION):
    raise SystemExit('Invalid load parameters')
PROFILE = os.environ.get('AWS_PROFILE', 'academy-sandbox')
REGION = os.environ.get('AWS_REGION', 'us-east-1')
OUT = ROOT / 'results' / RUN_ID
def prepare_output():
    try:
        OUT.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit(
            f'RUN_ID already exists, refusing overwrite: {OUT}'
        )
PREFIX = f's3://{BUCKET}/experiments/exp002_component_capacity/results/{RUN_ID}'

def now():
    return datetime.now(timezone.utc)

def iso(t):
    return t.isoformat().replace('+00:00', 'Z')

def aws(*args):
    cmd = ['aws', '--profile', PROFILE, '--region', REGION, *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'AWS command failed: {args[:3]}: {result.stderr[:400]}')
    return result.stdout.strip()

def aws_json(*args):
    return json.loads(aws(*args))

def ssm(instance, commands, label):
    command_id = aws('ssm', 'send-command', '--instance-ids', instance,
        '--document-name', 'AWS-RunShellScript', '--comment', f'EXP-002 {label} {RUN_ID}',
        '--parameters', json.dumps({'commands': commands}), '--query', 'Command.CommandId', '--output', 'text')
    return command_id

def await_ssm(instance, cid, timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = aws_json('ssm', 'get-command-invocation', '--command-id', cid, '--instance-id', instance)
        except RuntimeError:
            time.sleep(3)
            continue
        if result['Status'] in ('Success', 'Failed', 'Cancelled', 'TimedOut', 'Cancelling'):
            if result['Status'] != 'Success':
                raise RuntimeError(f'SSM {cid} {result["Status"]}: {result.get("StandardErrorContent", "")[:300]}')
            return result
        time.sleep(3)
    raise TimeoutError(f'SSM command timeout: {cid}')

def snapshot(stage, instance, role):
    command = '''set -eu
python3 - <<'SNAP'
import json,os,time
from pathlib import Path
m=Path('/proc/meminfo').read_text().splitlines()
mem={k:int(v.strip().split()[0]) for k,v in (line.split(':',1) for line in m)}
print(json.dumps({'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'loadavg':Path('/proc/loadavg').read_text().strip(),'memory_total_kib':mem.get('MemTotal'),'memory_available_kib':mem.get('MemAvailable'),'role':os.uname().nodename}))
SNAP'''
    result = await_ssm(instance, ssm(instance, [command], f'{stage}-{role}'))
    data = result['StandardOutputContent'].strip()
    (OUT / f'linux_{stage}_{role}.json').write_text(data + '\n')

def cloudwatch(start, end):
    for instance, role in ((WORKLOAD, 'workload'), (LOCUST, 'locust')):
        for metric in ('CPUUtilization', 'NetworkIn', 'NetworkOut'):
            data = aws_json('cloudwatch', 'get-metric-statistics', '--namespace', 'AWS/EC2',
                '--metric-name', metric, '--dimensions', f'Name=InstanceId,Value={instance}',
                '--start-time', iso(start), '--end-time', iso(end), '--period', '60',
                '--statistics', 'Average', '--output', 'json')
            (OUT / f'cloudwatch_{role}_{metric}.json').write_text(json.dumps(data, indent=2) + '\n')

def load(ip):
    remote = f'/opt/exp002-locust/results/{RUN_ID}'
    locust_bin = f'/opt/exp002-locust/venvs/{BUNDLE}/bin/locust'
    cmd = f'''set -eu
mkdir -p '{remote}'
set +e
'{locust_bin}' -f /opt/exp002-locust/locustfile.py --headless --host http://{ip}:8001 --users {USERS} --spawn-rate {SPAWN} --run-time {DURATION} --csv '{remote}/exp002' --exit-code-on-error 1
rc=$?
set -e
aws s3 sync '{remote}/' '{PREFIX}/' --sse AES256
exit "$rc"'''
    return ssm(LOCUST, [cmd], 'load')

def parse_stats():
    stats = OUT / 'exp002_stats.csv'
    if not stats.is_file():
        raise RuntimeError('Locust stats CSV missing')
    with stats.open(newline='') as f:
        rows = list(csv.DictReader(f))
    agg = next((r for r in rows if (r.get('Name') == 'Aggregated' or r.get('Type') == 'Aggregated')), None)
    if not agg:
        raise RuntimeError('Locust aggregated statistics missing')
    requests = int(agg['Request Count'])
    failures = int(agg['Failure Count'])
    p95 = float(agg['95%'])
    rps = float(agg['Requests/s'])
    observations = {'request_count': requests, 'error_rate': failures / requests if requests else 1.0,
        'latency_p95_ms': p95, 'throughput_rps': rps}
    policy = {'max_latency_p95_ms': float(os.environ.get('SLA_P95_MS', '1000')),
        'max_error_rate': float(os.environ.get('SLA_ERROR_RATE', '0.01')),
        'min_throughput_rps': float(os.environ.get('SLA_MIN_RPS', '1'))}
    status = ('PASS' if requests and p95 <= policy['max_latency_p95_ms']
        and observations['error_rate'] <= policy['max_error_rate']
        and rps >= policy['min_throughput_rps'] else 'FAIL')
    (OUT / 'metrics_normalized.json').write_text(json.dumps({'experiment_id':'EXP-002','run_id':RUN_ID,'observations':observations},indent=2)+'\n')
    (OUT / 'sla_evaluation.json').write_text(json.dumps({'experiment_id':'EXP-002','run_id':RUN_ID,'policy':policy,'overall_status':status},indent=2)+'\n')
    return status

def archive():
    files = {}
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != 'evidence_manifest.json':
            b=p.read_bytes()
            files[p.name]={'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)}
    manifest={'schema_version':'1.0','experiment_id':'EXP-002','run_id':RUN_ID,
        'archive_status':'COMPLETE','files':files,'archived_at_utc':iso(now())}
    (OUT/'evidence_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    aws('s3','sync',str(OUT)+'/',PREFIX+'/', '--sse','AES256')
    remote = aws('s3','cp',PREFIX+'/evidence_manifest.json','-')
    if json.loads(remote) != manifest:
        raise RuntimeError('S3 manifest mismatch')
    return PREFIX

def main():
    prepare_output()
    ip = aws('ec2','describe-instances','--instance-ids',WORKLOAD,
        '--query','Reservations[0].Instances[0].PrivateIpAddress','--output','text')
    if not re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}',ip):
        raise RuntimeError('Invalid private IP')
    (OUT/'run_manifest.json').write_text(json.dumps({'experiment_id':'EXP-002','run_id':RUN_ID,
        'started_at_utc':iso(now()),'workload_instance_id':WORKLOAD,
        'locust_instance_id':LOCUST,'users':USERS,'spawn_rate':SPAWN,'duration':DURATION},indent=2)+'\n')
    print('EXP-002 PRE: 60s monitoring window',flush=True)
    pre_start=now()
    snapshot('PRE',WORKLOAD,'workload');snapshot('PRE',LOCUST,'locust')
    time.sleep(max(0,60-(now()-pre_start).total_seconds()))
    print('EXP-002 RUN',flush=True)
    run_start=now()
    cid=load(ip)
    snapshot('RUN',WORKLOAD,'workload');snapshot('RUN',LOCUST,'locust')
    await_ssm(LOCUST,cid,timeout=max(600,int(DURATION[:-1])+180))
    run_end=now()
    print('EXP-002 POST: 60s monitoring window',flush=True)
    post_start=now()
    snapshot('POST',WORKLOAD,'workload');snapshot('POST',LOCUST,'locust')
    time.sleep(max(0,60-(now()-post_start).total_seconds()))
    post_end=now()
    cloudwatch(pre_start,post_end)
    aws('s3','cp',PREFIX+'/',str(OUT)+'/', '--recursive','--no-progress')
    status=parse_stats()
    target=archive()
    print(f'EXP002_RUN_COMPLETE run={RUN_ID} sla={status} evidence={target}')

if __name__ == '__main__':
    main()
