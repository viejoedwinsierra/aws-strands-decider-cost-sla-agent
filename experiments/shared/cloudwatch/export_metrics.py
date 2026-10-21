#!/usr/bin/env python3
"""Export AWS/EC2 CloudWatch metrics for arbitrary EC2 instances.

Read-only AWS calls. JSON files are written locally; S3 upload is not part of V1.1.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / 'config' / 'metrics_catalog.json'
# Units documented by the AWS/EC2 metric definitions; not inferred from a datapoint.
KNOWN_UNITS = {
    'CPUUtilization': 'Percent',
    'CPUCreditBalance': 'Count',
    'CPUCreditUsage': 'Count',
    'CPUSurplusCreditBalance': 'Count',
    'CPUSurplusCreditsCharged': 'Count',
    'NetworkIn': 'Bytes',
    'NetworkOut': 'Bytes',
    'NetworkPacketsIn': 'Count',
    'NetworkPacketsOut': 'Count',
    'EBSReadOps': 'Count',
    'EBSWriteOps': 'Count',
    'EBSReadBytes': 'Bytes',
    'EBSWriteBytes': 'Bytes',
    'StatusCheckFailed': 'Count',
    'StatusCheckFailed_Instance': 'Count',
    'StatusCheckFailed_System': 'Count',
}
INSTANCE_ID_RE = re.compile(r'^i-(?:[0-9a-f]{8}|[0-9a-f]{17})$')


def utc_datetime(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Timezone is required')
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f'Invalid timezone-aware ISO 8601 timestamp: {value}'
        ) from exc


def utc_iso(value):
    parsed = utc_datetime(value)
    return parsed.isoformat(timespec='seconds').replace('+00:00', 'Z')


def aws_json(arguments, profile, region):
    command = ['aws', *arguments, '--region', region, '--output', 'json']
    if profile:
        command.extend(['--profile', profile])
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError('AWS CLI executable not found') from exc
    if result.returncode:
        raise RuntimeError(f'AWS CLI failed ({result.returncode}): {result.stderr.strip()}')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('AWS CLI returned invalid JSON') from exc


def validate_catalog(catalog):
    if not isinstance(catalog, dict) or catalog.get('namespace') != 'AWS/EC2':
        raise ValueError('Catalog must declare namespace AWS/EC2')
    metrics = catalog.get('metrics')
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError('Catalog metrics must be a non-empty object')
    allowed_stats = {'Average', 'Sum', 'Minimum', 'Maximum', 'SampleCount'}
    for name, stats in metrics.items():
        if not isinstance(name, str) or not name or not isinstance(stats, list) or not stats:
            raise ValueError(f'Invalid metric definition: {name!r}')
        if len(stats) != len(set(stats)) or not set(stats).issubset(allowed_stats):
            raise ValueError(f'Invalid or duplicate statistics for {name}')
    count = sum(len(stats) for stats in metrics.values())
    if count > 500:
        raise ValueError(f'Too many query series ({count}); maximum is 500 per request')
    period = catalog.get('default_period_seconds')
    if type(period) is not int or period < 60 or period % 60:
        raise ValueError('Invalid default_period_seconds')


def build_queries(catalog, instance_id, period):
    queries, definitions = [], {}
    for metric_name, statistics in catalog['metrics'].items():
        for statistic in statistics:
            query_id = f'm{len(queries)}'
            queries.append({
                'Id': query_id,
                'MetricStat': {
                    'Metric': {
                        'Namespace': catalog['namespace'],
                        'MetricName': metric_name,
                        'Dimensions': [{'Name': 'InstanceId', 'Value': instance_id}],
                    },
                    'Period': period,
                    'Stat': statistic,
                },
                'ReturnData': True,
            })
            definitions[query_id] = {'metric': metric_name, 'statistic': statistic}
    return queries, definitions


def collect_results(args, queries):
    base = [
        'cloudwatch', 'get-metric-data',
        '--start-time', args.start_time.isoformat(),
        '--end-time', args.end_time.isoformat(),
        '--metric-data-queries', json.dumps(queries),
        '--scan-by', 'TimestampAscending',
        '--no-paginate',
    ]
    results = []
    next_token = None
    seen_tokens = set()
    while True:
        command = base + (['--next-token', next_token] if next_token else [])
        page = aws_json(command, args.profile, args.region)
        results.extend(page.get('MetricDataResults', []))
        next_token = page.get('NextToken')
        if not next_token:
            return results
        if next_token in seen_tokens:
            raise RuntimeError('CloudWatch pagination returned a repeated NextToken')
        seen_tokens.add(next_token)


def normalize_series(results, definitions):
    series_by_id = {}
    for result in results:
        query_id = result.get('Id')
        if query_id not in definitions:
            raise RuntimeError(f'Unexpected CloudWatch query ID: {query_id!r}')
        timestamps, values = result.get('Timestamps', []), result.get('Values', [])
        if len(timestamps) != len(values):
            raise RuntimeError(f'Mismatched timestamps and values for {query_id}')
        series = series_by_id.setdefault(query_id, {
            'cloudwatch_statuses': [], 'messages': [], 'points': {}, 'returned_unit': None,
        })
        status = result.get('StatusCode')
        if status:
            series['cloudwatch_statuses'].append(status)
        series['messages'].extend(result.get('Messages', []))
        unit = result.get('Unit')
        if unit:
            if series['returned_unit'] and series['returned_unit'] != unit:
                raise RuntimeError(f'Inconsistent units for {query_id}')
            series['returned_unit'] = unit
        for timestamp, value in zip(timestamps, values):
            normalized = utc_iso(timestamp)
            previous = series['points'].get(normalized)
            if previous is not None and previous != value:
                raise RuntimeError(f'Conflicting datapoints for {query_id} at {normalized}')
            series['points'][normalized] = value

    metrics = {}
    for query_id, definition in definitions.items():
        name, statistic = definition['metric'], definition['statistic']
        series = series_by_id.get(query_id, {})
        points = series.get('points', {})
        timestamps = sorted(points)
        statuses = series.get('cloudwatch_statuses', [])
        if any(s not in ('Complete',) for s in statuses):
            status = 'incomplete'
        elif not timestamps:
            status = 'no_data'
        else:
            status = 'complete'
        unit = series.get('returned_unit') or KNOWN_UNITS.get(name)
        metrics.setdefault(name, {})[statistic] = {
            'unit': unit,
            'unit_source': 'cloudwatch' if series.get('returned_unit') else (
                'metric_definition' if unit else 'unavailable'
            ),
            'status': status,
            'cloudwatch_statuses': sorted(set(statuses)),
            'datapoint_count': len(timestamps),
            'first_timestamp_utc': timestamps[0] if timestamps else None,
            'last_timestamp_utc': timestamps[-1] if timestamps else None,
            'datapoints': [{'timestamp': t, 'value': points[t]} for t in timestamps],
            'messages': series.get('messages', []),
        }
    return metrics


def export_instance(args, catalog, instance_id):
    queries, definitions = build_queries(catalog, instance_id, args.period)
    results = collect_results(args, queries)
    metrics = normalize_series(results, definitions)
    return {
        'schema_version': '1.1',
        'source': 'Amazon CloudWatch GetMetricData',
        'experiment': args.experiment,
        'run_id': args.run_id,
        'instance_id': instance_id,
        'region': args.region,
        'catalog_version': catalog['version'],
        'namespace': catalog['namespace'],
        'period_seconds': args.period,
        'requested_window': {
            'start_utc': utc_iso(args.start_time.isoformat()),
            'end_utc': utc_iso(args.end_time.isoformat()),
        },
        'exported_at_utc': utc_iso(datetime.now(timezone.utc).isoformat()),
        'coverage_note': (
            'First/last timestamps describe observed datapoints only; '
            'they do not establish continuous coverage of the requested window.'
        ),
        'metrics': metrics,
    }


def main():
    parser = argparse.ArgumentParser(description='Export CloudWatch EC2 metrics to local JSON.')
    parser.add_argument('--instance-ids', nargs='+', required=True)
    parser.add_argument('--start-time', type=utc_datetime, required=True)
    parser.add_argument('--end-time', type=utc_datetime, required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--profile')
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--catalog', type=Path, default=DEFAULT_CATALOG)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--period', type=int)
    args = parser.parse_args()
    if args.end_time <= args.start_time:
        parser.error('--end-time must be later than --start-time')
    if any(not INSTANCE_ID_RE.fullmatch(i) for i in args.instance_ids):
        parser.error('--instance-ids must contain valid EC2 instance IDs')
    catalog = json.loads(args.catalog.read_text(encoding='utf-8'))
    validate_catalog(catalog)
    if args.period is None:
        args.period = catalog['default_period_seconds']
    if args.period < 60 or args.period % 60:
        parser.error('--period must be a positive multiple of 60 seconds')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for instance_id in dict.fromkeys(args.instance_ids):
        print(f'Exporting CloudWatch metrics: {instance_id}')
        evidence = export_instance(args, catalog, instance_id)
        destination = args.output_dir / f'{instance_id}.json'
        destination.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
        )
        print(f'Saved: {destination}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
