#!/usr/bin/env python3
"""Finalize EXP-001 CloudWatch campaign using existing exporter; archive in S3."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
EXPORTER = BASE.parent / 'shared' / 'cloudwatch' / 'export_metrics.py'
CATALOG = BASE.parent / 'shared' / 'config' / 'metrics_catalog.json'


def aws(args, profile, region, capture=False):
    cmd = ['aws', '--profile', profile, '--region', region, *args]
    return subprocess.run(cmd, check=True, capture_output=capture)


def save(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('campaign-id', 'pre-start', 'pre-end', 'post-start', 'post-end', 'inventory', 'profile', 'region', 'bucket'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--period', type=int, default=300)
    args = parser.parse_args()
    if not re.fullmatch(r'exp001_[0-9]{8}T[0-9]{6}[0-9]+Z', args.campaign_id):
        parser.error('Invalid campaign ID')
    if args.period < 60 or args.period % 60:
        parser.error('Period must be multiple of 60')
    def parse(value):
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is None:
            raise ValueError('UTC offset required')
        return d.astimezone(timezone.utc)
    timestamps = [parse(x) for x in (args.pre_start, args.pre_end, args.post_start, args.post_end)]
    if timestamps != sorted(timestamps) or len(set(timestamps)) != 4:
        parser.error('Invalid PRE/RUN/POST ordering')
    directory = BASE / 'results' / 'campaigns' / args.campaign_id
    summary_path = directory / 'campaign_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if summary.get('campaign_id') != args.campaign_id:
        raise ValueError('Campaign summary ID mismatch')
    inventory = json.loads(Path(args.inventory).read_text(encoding='utf-8'))
    ids = [item['instance_id'] for item in inventory['instances']]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Empty or duplicate EC2 inventory')
    if not {'http-server', 'load-generator'}.issubset({i.get('role') for i in inventory['instances']}):
        raise ValueError('Missing required EC2 roles')
    timeline = {
        'schema_version': '1.0', 'campaign_id': args.campaign_id,
        'phases': {
            'PRE': {'start_utc': args.pre_start, 'end_utc': args.pre_end},
            'RUN': {'start_utc': args.pre_end, 'end_utc': args.post_start},
            'POST': {'start_utc': args.post_start, 'end_utc': args.post_end},
        },
        'cloudwatch_window': {'start_utc': args.pre_start, 'end_utc': args.post_end},
        'scenarios': [{k: record.get(k) for k in ('scenario_id', 'run_id', 'started_at_utc', 'finished_at_utc')} for record in summary['scenarios']],
    }
    directory.mkdir(parents=True, exist_ok=True)
    save(directory / 'experiment_timeline.json', timeline)
    cwdir = directory / 'cloudwatch'
    cmd = [sys.executable, str(EXPORTER), '--instance-ids', *ids, '--start-time', args.pre_start,
           '--end-time', args.post_end, '--region', args.region, '--profile', args.profile,
           '--experiment', 'EXP-001', '--run-id', args.campaign_id, '--catalog', str(CATALOG),
           '--output-dir', str(cwdir), '--period', str(args.period)]
    summary['observability_status'] = 'COLLECTING'
    save(summary_path, summary)
    try:
        subprocess.run(cmd, check=True)
        series_report = {}
        for instance_id in ids:
            data = json.loads((cwdir / f'{instance_id}.json').read_text(encoding='utf-8'))
            if data.get('instance_id') != instance_id:
                raise ValueError(f'Unexpected EC2 identity: {instance_id}')
            stats = [stat for group in data['metrics'].values() for stat in group.values()]
            total = sum(item['datapoint_count'] for item in stats)
            if total == 0:
                raise ValueError(f'No CloudWatch datapoints for {instance_id}')
            series_report[instance_id] = {'series': len(stats), 'datapoints': total,
                                          'no_data_series': sum(item['status'] == 'no_data' for item in stats)}
        # S3 is the source of truth; upload before verifying remote SHA-256.
        prefix = f'experiments/exp001_capacity/results/campaigns/{args.campaign_id}'
        paths = [Path(args.inventory), directory / 'experiment_timeline.json',
                 *[cwdir / f'{i}.json' for i in ids]]
        names = ['ec2_inventory.json', 'experiment_timeline.json', *[f'cloudwatch/{i}.json' for i in ids]]
        manifest = {'schema_version': '1.0', 'campaign_id': args.campaign_id,
                    'files': {name: {'size_bytes': path.stat().st_size,
                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                              for name, path in zip(names, paths)}}
        save(directory / 'campaign_evidence_manifest.json', manifest)
        paths.append(directory / 'campaign_evidence_manifest.json')
        names.append('campaign_evidence_manifest.json')
        for path, name in zip(paths, names):
            key = f'{prefix}/{name}'
            aws(['s3', 'cp', str(path), f's3://{args.bucket}/{key}', '--sse', 'AES256', '--no-progress'], args.profile, args.region)
            result = aws(['s3', 'cp', f's3://{args.bucket}/{key}', '-', '--no-progress'], args.profile, args.region, capture=True)
            if hashlib.sha256(result.stdout).digest() != hashlib.sha256(path.read_bytes()).digest():
                raise ValueError(f'S3 SHA-256 mismatch: {name}')
        summary['observability_status'] = 'EXPORTED_VERIFIED'
        summary['cloudwatch'] = {'period_seconds': args.period, 'instances': series_report,
                                 's3_prefix': f's3://{args.bucket}/{prefix}/'}
        summary['status'] = 'COMPLETED' if summary['status'] == 'LOAD_COMPLETED' else summary['status']
        save(summary_path, summary)
        aws(['s3', 'cp', str(summary_path), f's3://{args.bucket}/{prefix}/campaign_summary.json',
             '--sse', 'AES256', '--no-progress'], args.profile, args.region)
        print('CAMPAIGN_OBSERVABILITY_VERIFIED:', args.campaign_id)
        return 0
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
        summary['observability_status'] = 'FAILED'
        summary['observability_error'] = str(exc)
        summary['status'] = 'INCOMPLETE' if summary['status'] == 'LOAD_COMPLETED' else summary['status']
        save(summary_path, summary)
        print('CAMPAIGN_OBSERVABILITY_FAILED:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
