#!/usr/bin/env python3
"""EXP-001 evidence quality gate. Runs after CloudWatch restoration and S3 archiving."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


def parse_time(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def check_remote(profile, region, bucket, key, path):
    cmd = ['aws', '--profile', profile, '--region', region, 's3', 'cp',
           f's3://{bucket}/{key}', '-', '--no-progress']
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode:
        return False, p.stderr.decode(errors='replace')[:200]
    return hashlib.sha256(p.stdout).digest() == hashlib.sha256(path.read_bytes()).digest(), 'sha256'


def main():
    p = argparse.ArgumentParser()
    for name in ('campaign-id', 'campaign-dir', 'bucket', 'profile', 'region', 'pre-start', 'pre-end', 'post-start', 'post-end', 'http-id', 'locust-id'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--experiment', choices=['EXP-001','EXP-002'], default='EXP-001')
    a = p.parse_args()
    root = Path(a.campaign_dir)
    folder = 'exp001_capacity' if a.experiment == 'EXP-001' else 'exp002_component_capacity'
    prefix = f'experiments/{folder}/results/campaigns/{a.campaign_id}/'
    phases = {'PRE': (parse_time(a.pre_start), parse_time(a.pre_end)),
              'RUN': (parse_time(a.pre_end), parse_time(a.post_start)),
              'POST': (parse_time(a.post_start), parse_time(a.post_end))}
    report = {'campaign_id': a.campaign_id, 'status': 'PASS', 'checks': {}, 'warnings': []}
    def warn(code, detail):
        report['warnings'].append({'code': code, 'detail': detail})
    def check(name, ok, detail):
        report['checks'][name] = {'status': 'PASS' if ok else 'FAIL', 'detail': detail}
        if not ok:
            report['status'] = 'FAIL'
    expected = ['ec2_inventory.json', 'experiment_timeline.json', 'campaign_summary.json',
                'campaign_evidence_manifest.json', 'detailed_monitoring_state.json',
                f'cloudwatch/{a.http_id}.json', f'cloudwatch/{a.locust_id}.json',
                f'linux/{a.http_id}.jsonl', f'linux/{a.locust_id}.jsonl',
                'linux/linux_monitor_report.json']
    for rel in expected:
        path = root / rel
        exists = path.is_file() and path.stat().st_size > 0
        check(f'local:{rel}', exists, 'nonempty' if exists else 'missing/empty')
        if exists:
            ok, detail = check_remote(a.profile, a.region, a.bucket, prefix + rel, path)
            check(f's3:{rel}', ok, detail)
    journal = root / 'detailed_monitoring_state.json'
    if journal.is_file():
        data = json.loads(journal.read_text())
        check('detailed_monitoring_restored', data.get('status') == 'RESTORED' and
              all(v.get('restored') for v in data.get('instances', {}).values()), data.get('status'))
    for iid in (a.http_id, a.locust_id):
        path = root / 'linux' / f'{iid}.jsonl'
        if not path.is_file():
            continue
        rows = []
        malformed = 0
        for line in path.read_text().splitlines():
            try:
                obj = json.loads(line)
                timestamp = parse_time(obj['timestamp_utc'])
                rows.append(timestamp)
            except (ValueError, KeyError, TypeError):
                malformed += 1
        check(f'linux_valid:{iid}', malformed == 0 and bool(rows),
              {'samples': len(rows), 'malformed': malformed})
        check(f'linux_unique:{iid}', len(rows) == len(set(rows)), {'duplicates': len(rows)-len(set(rows))})
        for phase, (start, end) in phases.items():
            count = sum(start <= timestamp < end for timestamp in rows)
            check(f'linux_{phase}:{iid}', count > 0, {'samples': count})
    # CloudWatch: enforce identity, metric structure and useful RUN evidence.
    # CloudWatch one-minute timestamps denote aggregated periods; PRE/POST
    # phase-level coverage is advisory, not a strict failure criterion.
    for iid in (a.http_id, a.locust_id):
        path = root / 'cloudwatch' / f'{iid}.json'
        if not path.is_file():
            continue  # Missing file already failed the local/S3 checks.
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('CloudWatch payload must be an object')
            check(f'cloudwatch_json:{iid}', True, 'valid JSON object')
            check(f'cloudwatch_identity:{iid}',
                  data.get('instance_id') == iid and data.get('experiment') == a.experiment
                  and data.get('run_id') == a.campaign_id,
                  {'instance_id': data.get('instance_id'), 'run_id': data.get('run_id')})
            period = data.get('period_seconds')
            check(f'cloudwatch_period:{iid}', isinstance(period, int) and period > 0,
                  {'period_seconds': period})
            metrics = data.get('metrics')
            if not isinstance(metrics, dict):
                raise ValueError('metrics must be an object')
            for metric, stat in (('CPUUtilization', 'Average'),
                                 ('NetworkIn', 'Sum'), ('NetworkOut', 'Sum')):
                series = metrics.get(metric, {}).get(stat, {})
                points = series.get('datapoints', []) if isinstance(series, dict) else []
                valid = isinstance(points, list) and bool(points)
                stamps = []
                if valid:
                    try:
                        for point in points:
                            timestamp = parse_time(point['timestamp'])
                            value = float(point['value'])
                            if not math.isfinite(value):
                                raise ValueError('nonfinite metric value')
                            stamps.append(timestamp)
                    except (KeyError, TypeError, ValueError, AttributeError):
                        valid = False
                if valid:
                    valid = (len(stamps) == len(set(stamps)) and
                             all(phases['PRE'][0] - dt.timedelta(seconds=period) <= t <=
                                 phases['POST'][1] for t in stamps))
                check(f'cloudwatch_series:{iid}:{metric}:{stat}', valid,
                      {'datapoints': len(points) if isinstance(points, list) else 0})
                if not valid:
                    continue
                # A period timestamp may precede the actual RUN by one period.
                run_start, run_end = phases['RUN']
                run_count = sum(run_start - dt.timedelta(seconds=period) <= t < run_end
                                for t in stamps)
                check(f'cloudwatch_RUN:{iid}:{metric}', run_count > 0,
                      {'candidate_datapoints': run_count, 'period_seconds': period})
                for phase in ('PRE', 'POST'):
                    start_time, end_time = phases[phase]
                    phase_count = sum(start_time - dt.timedelta(seconds=period) <= t < end_time
                                      for t in stamps)
                    if not phase_count:
                        warn(f'cloudwatch_{phase}:{iid}:{metric}',
                             'No timestamp overlapping phase at reported resolution')
            for metric in ('CPUCreditBalance', 'CPUCreditUsage'):
                if metric not in metrics:
                    warn(f'cloudwatch_optional:{iid}:{metric}', 'Metric unavailable')
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
            check(f'cloudwatch_json:{iid}', False, str(exc))
    # A campaign manifest is intentionally distinct from a full archive inventory.
    manifest_file = root / 'campaign_evidence_manifest.json'
    if manifest_file.is_file():
        try:
            listed = json.loads(manifest_file.read_text()).get('files', {})
            omitted = sorted(set(expected) - set(listed) - {'campaign_evidence_manifest.json'})
            if omitted:
                warn('campaign_manifest_incomplete', {'unlisted_files': omitted})
        except (ValueError, TypeError, AttributeError):
            warn('campaign_manifest_unreadable', 'Could not inspect manifest inventory')
    output = root / 'evidence_quality_report.json'
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    # Upload report even if quality gate fails, so failures are auditable.
    cmd = ['aws', '--profile', a.profile, '--region', a.region, 's3', 'cp', str(output),
           f's3://{a.bucket}/{prefix}evidence_quality_report.json', '--sse', 'AES256', '--no-progress']
    upload = subprocess.run(cmd, capture_output=True, text=True)
    if upload.returncode:
        print('EVIDENCE_QUALITY_REPORT_UPLOAD_FAILED:', upload.stderr.strip(), file=sys.stderr)
        report['status'] = 'FAIL'
        report['checks']['quality_report_upload'] = {'status': 'FAIL', 'detail': upload.stderr.strip()}
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('EVIDENCE_QUALITY_' + report['status'] + ':', output, flush=True)
    for name, item in report['checks'].items():
        if item['status'] == 'FAIL':
            print('  FAILED:', name, item['detail'], flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('EVIDENCE_QUALITY_FAILED:', exc, file=sys.stderr)
        sys.exit(1)
