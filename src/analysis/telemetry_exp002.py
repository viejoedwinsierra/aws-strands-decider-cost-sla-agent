"""Read-only EXP-002 adapter to the existing EXP-001 telemetry summary shape."""
import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def observed_window(campaign, run_dir, run_id):
    timeline = campaign / 'experiment_timeline.json'
    if timeline.is_file():
        matches = [s for s in load(timeline).get('scenarios', []) if s.get('run_id') == run_id]
        if len(matches) == 1:
            item = matches[0]
            if item.get('started_at_utc') and item.get('finished_at_utc'):
                start, end = timestamp(item['started_at_utc']), timestamp(item['finished_at_utc'])
                if end > start:
                    return start, end, 'campaign_timeline', 'declared'
    csv_path = run_dir / 'exp002_stats_history.csv'
    if not csv_path.is_file():
        raise ValueError(f'No observed scenario window: {run_id}')
    samples = []
    with csv_path.open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            if row.get('Name') == 'Aggregated' and row.get('Timestamp'):
                try:
                    if float(row.get('User Count') or 0) > 0:
                        samples.append(timestamp(float(row['Timestamp'])))
                except (ValueError, OverflowError):
                    continue
    if len(samples) < 2 or max(samples) <= min(samples):
        raise ValueError(f'Insufficient observed Locust timestamps: {run_id}')
    return min(samples), max(samples), 'locust_stats_history_observed', 'observed_samples_not_exact_execution_boundaries'


def stats(values):
    return {'sample_count': len(values), 'mean': sum(values)/len(values) if values else None,
            'minimum': min(values) if values else None, 'maximum': max(values) if values else None}


def summarize_exp002(campaign, run_dir, run_id):
    campaign, run_dir = Path(campaign), Path(run_dir)
    start, end, window_source, window_quality = observed_window(campaign, run_dir, run_id)
    inventory_path = campaign / 'ec2_inventory.json'
    if not inventory_path.is_file():
        raise ValueError(f'Missing EC2 role inventory: {campaign}')
    inventory = load(inventory_path)
    role_ids = {}
    for item in inventory.get('instances', []):
        role = item.get('role', '')
        if role == 'workload-server': role_ids['workload'] = item['instance_id']
        if role == 'load-generator': role_ids['locust'] = item['instance_id']
    if len(role_ids) != 2:
        raise ValueError('EXP-002 requires workload and locust instance identities')
    cloudwatch, linux = {}, {}
    for role, instance_id in role_ids.items():
        cloudwatch[instance_id] = {}
        for path in sorted(run_dir.glob(f'cloudwatch_{role}_*.json')):
            doc = load(path)
            metric = path.stem[len(f'cloudwatch_{role}_'):]
            values = {}
            # AWS GetMetricStatistics timestamps mark aggregation period starts.
            # A sample is included only when its bucket overlaps the observed window.
            period = int(doc.get('PeriodSeconds') or doc.get('period_seconds') or 60)
            if period <= 0: raise ValueError('Invalid CloudWatch period')
            for point in doc.get('Datapoints', []):
                if 'Timestamp' not in point: continue
                point_time = timestamp(point['Timestamp'])
                if point_time > end or point_time + timedelta(seconds=period) <= start: continue
                for key in ('Average', 'Maximum', 'Minimum', 'Sum'):
                    value = point.get(key)
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        values.setdefault(key, []).append(float(value))
            cloudwatch[instance_id][metric] = {key: stats(numbers) for key, numbers in values.items()}
        memory_values = []
        count = 0
        for path in sorted(run_dir.glob(f'linux_*_{role}.json')):
            item = load(path)
            if not isinstance(item, dict) or not item.get('timestamp_utc'): continue
            moment = timestamp(item['timestamp_utc'])
            if start <= moment <= end:
                count += 1
                total, available = item.get('memory_total_kib'), item.get('memory_available_kib')
                if isinstance(total, (int, float)) and isinstance(available, (int, float)) and total > 0 and 0 <= available <= total:
                    memory_values.append(100 * (1 - available/total))
        mem = stats(memory_values)
        linux[instance_id] = {'source': 'Linux SSM snapshots', 'snapshot_count': count,
            'cpu_utilization_percent': {'sample_count': 0, 'mean': None, 'maximum': None,
                                        'derivation': 'unavailable_no_cpu_jiffies'},
            'memory_utilization_percent': {**mem, 'derivation': 'MemAvailable/MemTotal'}}
    return {'run_id': run_id,
            'window': {'started_at_utc': start.isoformat(), 'finished_at_utc': end.isoformat(),
                       'source': window_source, 'quality': window_quality},
            'cloudwatch': cloudwatch, 'linux': linux,
            'provenance': {'source_format': 'exp002_per_run', 'cloudwatch_period_assumption_seconds': 60,
                           'originals_modified': False}}
