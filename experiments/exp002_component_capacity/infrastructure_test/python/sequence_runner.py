#!/usr/bin/env python3
"""EXP-002 scenario campaign; delegates AWS runs to the existing EXP-002 runner.
Dry-run is fully offline; live run requires explicit --execute and account profile.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def parse_sequence(path):
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit('PyYAML unavailable; reuse the existing agent venv, no automatic download') from exc
    with path.open(encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or data.get('experiment_id') != 'EXP-002':
        raise ValueError('Expected EXP-002 YAML')
    execution = data.get('execution') or {}
    if execution.get('mode', 'sequential') != 'sequential':
        raise ValueError('Only sequential mode is supported')
    scenarios = data.get('scenarios')
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError('At least one scenario required')
    if not isinstance(execution.get("stop_on_failure", True), bool):
        raise ValueError("stop_on_failure must be boolean")
    ids = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not re.fullmatch(r'[A-Za-z0-9_-]+', str(scenario.get('id', ''))):
            raise ValueError('Invalid scenario id')
        if scenario['id'] in ids:
            raise ValueError('Duplicate scenario id')
        ids.add(scenario['id'])
        if type(scenario.get('users')) is not int or scenario['users'] < 1:
            raise ValueError('Invalid users')
        if float(scenario.get('spawn_rate', 0)) <= 0:
            raise ValueError('Invalid spawn_rate')
        if not re.fullmatch(r'[1-9][0-9]*s', str(scenario.get('duration', ''))):
            raise ValueError('Invalid duration')
        http = scenario.get('http')
        if http is not None:
            if not isinstance(http, dict) or not isinstance(http.get('operations'), list) or not http['operations']:
                raise ValueError('http.operations must be a nonempty list')
            for op in http['operations']:
                if not isinstance(op, dict) or op.get('method') not in ('GET','POST','PUT','PATCH','DELETE'):
                    raise ValueError('Invalid HTTP method')
                if not isinstance(op.get('path'), str) or not op['path'].startswith('/') or '://' in op['path']:
                    raise ValueError('Invalid HTTP path')
                if type(op.get('weight', 1)) is not int or op.get('weight', 1) < 1:
                    raise ValueError('Invalid HTTP weight')
                if not isinstance(op.get('timeout', 10), (int,float)) or isinstance(op.get('timeout',10),bool) or not 0 < op.get('timeout',10) <= 120:
                    raise ValueError('Invalid HTTP timeout')
                if op.get('payload') is not None and not isinstance(op['payload'], dict):
                    raise ValueError('Invalid HTTP payload')
                if op.get('params') is not None and not isinstance(op['params'], dict):
                    raise ValueError('Invalid HTTP params')
        sla = scenario.get('sla', {})
        if not isinstance(sla, dict) or any(k not in ('max_latency_p95_ms','max_error_rate','min_throughput_rps') for k in sla):
            raise ValueError('Invalid SLA policy')
        for k,v in sla.items():
            if isinstance(v,bool) or not isinstance(v,(int,float)) or v < 0 or (k=='max_error_rate' and v > 1):
                raise ValueError('Invalid SLA threshold')
    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=ROOT / 'config/test_sequence.yml')
    parser.add_argument('--campaign-id', default=None)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    data = parse_sequence(args.config)
    print(json.dumps({'experiment_id':'EXP-002','mode':'execute' if args.execute else 'dry-run',
                      'scenarios':data['scenarios']},indent=2), flush=True)
    if args.dry_run:
        print('EXP002_CAMPAIGN_DRY_RUN_PASS')
        return
    profile = os.environ.get('AWS_PROFILE', '')
    if not profile or profile == 'REPLACE_WITH_AWS_PROFILE':
        raise SystemExit('Explicit AWS_PROFILE required')
    if not os.environ.get('EVIDENCE_BUCKET'):
        raise SystemExit('EVIDENCE_BUCKET required for AWS campaign')
    campaign = args.campaign_id or ('exp002_campaign_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if not re.fullmatch(r'exp002_campaign_[0-9]{8}T[0-9]{6}Z', campaign):
        raise SystemExit('Invalid campaign ID')
    directory = ROOT / 'results/campaigns' / campaign
    if directory.exists():
        marker = directory / '.orchestrator_owner'
        if not args.campaign_id or not marker.is_file():
            raise SystemExit('Campaign already exists')
        if marker.read_text().strip() != campaign:
            raise SystemExit('Campaign ownership mismatch')
        if (directory / 'campaign_manifest.json').exists():
            raise SystemExit('Campaign already executed')
        marker.unlink()
    else:
        directory.mkdir(parents=True)
    outcomes = []
    try:
        for index, scenario in enumerate(data['scenarios']):
            env = os.environ.copy()
            env.update({'RUN_ID':f'{campaign}_{scenario["id"]}', 'USERS':str(scenario['users']),
                        'SPAWN_RATE':str(scenario['spawn_rate']), 'DURATION':scenario['duration']})
            if 'http' in scenario:
                env['EXP002_HTTP_CONFIG'] = json.dumps(scenario['http'], separators=(',', ':'))
            for key, value in scenario.get('sla', {}).items():
                env[{'max_latency_p95_ms':'SLA_P95_MS','max_error_rate':'SLA_ERROR_RATE','min_throughput_rps':'SLA_MIN_RPS'}[key]] = str(value)
            result = subprocess.run([sys.executable,str(ROOT/'infrastructure/run_experiment.py')],env=env,check=False)
            outcomes.append({'scenario':scenario['id'],'run_id':env['RUN_ID'],'exit_code':result.returncode})
            if result.returncode and data.get('execution',{}).get('stop_on_failure',True):
                break
            if index < len(data['scenarios'])-1:
                time.sleep(max(0,int(data.get('execution',{}).get('cooldown_seconds',0))))
    finally:
        manifest = {'schema_version':'1.0','experiment_id':'EXP-002','campaign_id':campaign,
                    'source_config':args.config.name,'runs':outcomes}
        summary = {'schema_version':'1.0','experiment_id':'EXP-002', 'campaign_id':campaign,
                   'status':'LOAD_COMPLETED' if len(outcomes)==len(data['scenarios']) and all(x['exit_code']==0 for x in outcomes) else 'INCOMPLETE',
                   'scenarios':[{'scenario_id':x['scenario'],'run_id':x['run_id'],
                                 'status':'COMPLETED' if x['exit_code']==0 else 'FAILED'} for x in outcomes]}
        (directory/'campaign_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        path = directory/'campaign_manifest.json'
        path.write_text(json.dumps(manifest,indent=2)+'\n')
        # S3 is mandatory for real runs, including incomplete campaigns.
        cmd=['aws','--profile',profile,'--region',os.environ.get('AWS_REGION','us-east-1'),
             's3','cp',str(path),f's3://{os.environ["EVIDENCE_BUCKET"]}/experiments/exp002_component_capacity/results/campaigns/{campaign}/campaign_manifest.json',
             '--sse','AES256','--no-progress']
        subprocess.run(cmd,check=True)
        subprocess.run(['aws','--profile',profile,'--region',os.environ.get('AWS_REGION','us-east-1'),'s3','cp',str(directory/'campaign_summary.json'),f's3://{os.environ["EVIDENCE_BUCKET"]}/experiments/exp002_component_capacity/results/campaigns/{campaign}/campaign_summary.json','--sse','AES256','--no-progress'],check=True)
    if len(outcomes) != len(data['scenarios']) or any(x['exit_code'] for x in outcomes):
        raise SystemExit('EXP002_CAMPAIGN_INCOMPLETE')
    print('EXP002_CAMPAIGN_COMPLETE',campaign)

if __name__ == '__main__':
    main()
