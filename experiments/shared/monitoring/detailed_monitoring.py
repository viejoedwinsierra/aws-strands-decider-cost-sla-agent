#!/usr/bin/env python3
"""Phase A: reversible EC2 detailed monitoring for one tagged experiment."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def aws(profile, region, *args):
    cmd = ['aws', '--profile', profile, '--region', region, *args, '--output', 'json', '--no-cli-pager']
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"AWS {' '.join(args[:2])}: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def atomic_write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def discover(profile, region, project, experiment, environment):
    filters = [f'Name=tag:Project,Values={project}', f'Name=tag:Experiment,Values={experiment}',
               'Name=instance-state-name,Values=running']
    if environment:
        filters.append(f'Name=tag:Environment,Values={environment}')
    response = aws(profile, region, 'ec2', 'describe-instances', '--filters', *filters)
    instances = [x for r in response.get('Reservations', []) for x in r.get('Instances', [])]
    output = {}
    for instance in instances:
        tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
        if tags.get('Project') != project or tags.get('Experiment') != experiment:
            raise RuntimeError('Ownership validation failed')
        if environment and tags.get('Environment') != environment:
            raise RuntimeError('Environment validation failed')
        iid = instance['InstanceId']
        output[iid] = {'role': tags.get('Role', ''), 'name': tags.get('Name', ''),
                       'original': instance.get('Monitoring', {}).get('State', 'unknown')}
    return dict(sorted(output.items()))


def states(profile, region, ids):
    if not ids:
        return {}
    result = aws(profile, region, 'ec2', 'describe-instances', '--instance-ids', *ids)
    return {x['InstanceId']: x.get('Monitoring', {}).get('State', 'unknown')
            for r in result.get('Reservations', []) for x in r.get('Instances', [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'enable', 'restore'])
    parser.add_argument('--profile', default=os.environ.get('AWS_PROFILE', 'academy-sandbox'))
    parser.add_argument('--region', default=os.environ.get('AWS_REGION', 'us-east-1'))
    parser.add_argument('--project', default=os.environ.get('PROJECT_TAG'))
    parser.add_argument('--experiment', default=os.environ.get('EXPERIMENT_ID', 'EXP-001'))
    parser.add_argument('--environment', default=os.environ.get('ENVIRONMENT', ''))
    parser.add_argument('--state-file', required=True, type=Path)
    parser.add_argument('--execute', action='store_true', help='Explicitly allow AWS monitoring changes')
    args = parser.parse_args()
    if not args.project or not args.experiment or '*' in args.project + args.experiment:
        parser.error('Explicit --project and --experiment are required')
    account = aws(args.profile, args.region, 'sts', 'get-caller-identity')['Account']
    scope = {'account': account, 'region': args.region, 'project': args.project,
             'experiment': args.experiment, 'environment': args.environment}
    path = args.state_file.resolve()
    if args.action == 'status':
        items = discover(args.profile, args.region, args.project, args.experiment, args.environment)
        print(json.dumps({'scope': scope, 'instances': items}, indent=2))
        if not items:
            raise RuntimeError('No running tagged EC2 instances found')
        return
    if args.action == 'enable':
        if path.exists():
            raise RuntimeError(f'State file already exists; restore or archive it first: {path}')
        items = discover(args.profile, args.region, args.project, args.experiment, args.environment)
        if not items:
            raise RuntimeError('No running tagged EC2 instances found')
        unknown = [i for i, d in items.items() if d['original'] not in ('enabled', 'disabled')]
        if unknown:
            raise RuntimeError(f'Unknown monitoring states: {unknown}')
        if not args.execute:
            print(json.dumps({'dry_run': True, 'scope': scope, 'instances': items}, indent=2))
            return
        journal = {'scope': scope, 'created_at': now(), 'status': 'ENABLING', 'instances': items}
        for entry in journal['instances'].values():
            entry['change_requested'] = False
            entry['restored'] = entry['original'] == 'enabled'
        atomic_write(path, journal)
        for iid, entry in journal['instances'].items():
            if entry['original'] == 'enabled':
                continue
            # Journal the intent before calling AWS so interrupted operations can be recovered.
            entry['change_requested'] = True
            atomic_write(path, journal)
            aws(args.profile, args.region, 'ec2', 'monitor-instances', '--instance-ids', iid)
        actual = states(args.profile, args.region, list(items))
        journal['observed_after_enable'] = actual
        journal['status'] = 'ENABLED' if all(v == 'enabled' for v in actual.values()) else 'ENABLE_UNVERIFIED'
        atomic_write(path, journal)
        print(json.dumps({'state_file': str(path), 'status': journal['status'], 'states': actual}, indent=2))
        if journal['status'] != 'ENABLED':
            raise RuntimeError('Enable could not be verified; use restore to recover')
        return
    if not path.exists():
        raise RuntimeError(f'State file not found: {path}')
    journal = json.loads(path.read_text(encoding='utf-8'))
    if journal.get('scope') != scope:
        raise RuntimeError('Account, region or tag scope mismatch with saved state')
    items = journal['instances']
    current = states(args.profile, args.region, list(items))
    if set(current) != set(items):
        raise RuntimeError('Some original instances no longer exist; manual review required')
    if not args.execute:
        print(json.dumps({'dry_run': True, 'restore_to': {i: e['original'] for i, e in items.items()},
                          'current': current}, indent=2))
        return
    journal['status'] = 'RESTORING'
    atomic_write(path, journal)
    for iid, entry in items.items():
        if entry['original'] == 'disabled' and entry.get('change_requested') and current[iid] == 'enabled':
            aws(args.profile, args.region, 'ec2', 'unmonitor-instances', '--instance-ids', iid)
        entry['restored'] = True if entry['original'] == 'enabled' else False
        atomic_write(path, journal)
    actual = states(args.profile, args.region, list(items))
    for iid, entry in items.items():
        entry['restored'] = actual.get(iid) == entry['original']
    journal['observed_after_restore'] = actual
    journal['status'] = 'RESTORED' if all(e['restored'] for e in items.values()) else 'RESTORE_UNVERIFIED'
    journal['restored_at'] = now()
    atomic_write(path, journal)
    print(json.dumps({'state_file': str(path), 'status': journal['status'], 'states': actual}, indent=2))
    if journal['status'] != 'RESTORED':
        raise RuntimeError('Restore not fully verified; retry restore')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
