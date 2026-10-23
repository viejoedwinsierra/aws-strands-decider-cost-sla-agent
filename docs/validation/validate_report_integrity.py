#!/usr/bin/env python3
"""Offline structural integrity checks for published InfraVita reports; no AWS or inference."""
from pathlib import Path
import json, csv, sys
ROOT = Path(__file__).resolve().parents[2]
ALL = {}
for experiment in ('001','002'):
    for provider,folder in (('local','local_model'),('bedrock','bedrock')):
        path = ROOT/'reports'/folder/f'exp{experiment}_{provider}.json'
        if not path.exists():
            sys.exit(f'MISSING_REPORT: {path}')
        obj=json.loads(path.read_text(encoding='utf-8'))
        decisions=obj.get('decisions',[])
        if obj.get('total_runs')!=10 or len(decisions)!=10:
            sys.exit(f'INVALID_RUN_COUNT: {path}')
        mapping={}
        for d in decisions:
            run=d.get('run_id'); h=d.get('evidence_sha256')
            if not run or not h or len(h)!=64 or run in mapping:
                sys.exit(f'INVALID_RUN_OR_HASH: {path}')
            mapping[run]=d
        ALL[(experiment,provider)]=mapping
for experiment in ('001','002'):
    a,b=ALL[(experiment,'local')],ALL[(experiment,'bedrock')]
    if a.keys()!=b.keys(): sys.exit(f'RUN_ID_MISMATCH: EXP-{experiment}')
    for run in a:
        if a[run]['evidence_sha256']!=b[run]['evidence_sha256']:
            sys.exit(f'EVIDENCE_HASH_MISMATCH: {run}')
        if a[run].get('sla_status')!=b[run].get('sla_status'):
            sys.exit(f'SLA_STATUS_MISMATCH: {run}')
        if experiment=='002' and a[run].get('sla_status')!='NOT_EVALUATED':
            sys.exit(f'UNEXPECTED_EXP002_SLA: {run}')
path=ROOT/'reports/comparison/comparison_by_run.csv'
if not path.exists():
    print('COMPARISON_CSV_NOT_PRESENT: JSON pairs verified')
else:
    with path.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    if len(rows)!=20 or len({r['run_id'] for r in rows})!=20:
        sys.exit('INVALID_COMPARISON_ROWS')
    for r in rows:
        experiment=r['experiment'].split('-')[-1]
        d=ALL[(experiment,'local')].get(r['run_id'])
        if d is None or d['evidence_sha256']!=r['evidence_sha256']:
            sys.exit(f'COMPARISON_HASH_MISMATCH: {r["run_id"]}')
print('OFFLINE_REPORT_INTEGRITY_PASS: 4 reports, 20 paired runs, 40 provider decisions')
print('LIMITATION: Structural consistency only; no external AWS provenance or model accuracy verification')
