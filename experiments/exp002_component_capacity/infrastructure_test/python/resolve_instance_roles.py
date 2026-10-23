#!/usr/bin/env python3
"""Resolve EXP-002 workload/Locust EC2 from shared tagged inventory."""
import json,sys
from pathlib import Path

def resolve(data):
    if data.get('experiment_id') != 'EXP-002':
        raise ValueError('Inventory must belong to EXP-002')
    instances=data.get('instances',[])
    roles={}
    for i in instances:
        role=i.get('role')
        if role in ('workload-server','load-generator'):
            if role in roles:
                raise ValueError('Duplicate EC2 role: '+role)
            if i.get('state') != 'running':
                raise ValueError('EC2 not running: '+str(i.get('instance_id')))
            roles[role]=i['instance_id']
    missing={'workload-server','load-generator'}-roles.keys()
    if missing: raise ValueError('Missing EC2 roles: '+','.join(sorted(missing)))
    return roles['workload-server'],roles['load-generator']

if __name__=='__main__':
    try:
        print('\n'.join(resolve(json.loads(Path(sys.argv[1]).read_text()))))
    except (ValueError,KeyError,IndexError) as exc:
        raise SystemExit('INVENTORY_ERROR: '+str(exc)) from exc
