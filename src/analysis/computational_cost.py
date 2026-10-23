"""Conservative computational consumption estimates from historical evidence.

Not monetary billing; a scenario mean is a proxy, not a sampled integral.
"""
import argparse
import json
import math
from datetime import datetime
from pathlib import Path


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _percentage(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 100


def _duration(window):
    start = datetime.fromisoformat(window['started_at_utc'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(window['finished_at_utc'].replace('Z', '+00:00'))
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError('Window timestamps must have timezone')
    seconds = (end - start).total_seconds()
    if not _positive(seconds):
        raise ValueError('Invalid scenario duration')
    return seconds


def _mean(contract, instance_id, metric, source, aggregation):
    matches = [m for m in contract['measurements']
               if m['instance_id'] == instance_id and m['metric'] == metric
               and m['source'] == source and m['aggregation'] == aggregation
               and m['quality'] in ('observed', 'derived')
               and (m['sample_count'] is None or m['sample_count'] > 0)
               and _percentage(m['value'])]
    return matches[0] if len(matches) == 1 else None


def calculate(record, inventory=None):
    """Return per-instance consumption estimates with explicit provenance.

    CloudWatch Average.mean preferred for CPU; Linux used only as fallback.
    Does not sum overlapping CPU sources, or aggregate distinct EC2 roles.
    Capacity is optional and must be explicitly supplied by the caller.
    """
    inventory = inventory or {}
    contract = record['telemetry_contract']
    seconds = _duration(contract['window'])
    ids = sorted({m['instance_id'] for m in contract['measurements'] if m['instance_id']})
    instances = []
    for instance_id in ids:
        cpu = (_mean(contract, instance_id, 'cpu_utilization', 'cloudwatch', 'Average.mean')
               or _mean(contract, instance_id, 'cpu_utilization', 'linux_ssm', 'mean'))
        memory = _mean(contract, instance_id, 'memory_utilization', 'linux_ssm', 'mean')
        capacity = inventory.get(instance_id, {})
        vcpu = capacity.get('vcpu')
        memory_gib = capacity.get('memory_gib')
        if vcpu is not None and (not isinstance(vcpu, int) or isinstance(vcpu, bool) or vcpu <= 0):
            raise ValueError(f'Invalid vCPU inventory for {instance_id}')
        if memory_gib is not None and not _positive(memory_gib):
            raise ValueError(f'Invalid memory inventory for {instance_id}')
        cpu_fraction = cpu['value'] / 100 if cpu else None
        memory_fraction = memory['value'] / 100 if memory else None
        instances.append({
            'instance_id': instance_id,
            'duration_seconds': seconds,
            'vcpu_capacity': vcpu,
            'memory_capacity_gib': memory_gib,
            'cpu_mean_percent': cpu['value'] if cpu else None,
            'cpu_source': cpu['source'] if cpu else None,
            'cpu_samples': cpu['sample_count'] if cpu else 0,
            'memory_mean_percent': memory['value'] if memory else None,
            'memory_source': memory['source'] if memory else None,
            'memory_samples': memory['sample_count'] if memory else 0,
            'cpu_utilization_percent_seconds_proxy': cpu['value'] * seconds if cpu else None,
            'cpu_used_vcpu_seconds_estimated': vcpu * seconds * cpu_fraction if cpu and vcpu else None,
            'cpu_idle_vcpu_seconds_estimated': vcpu * seconds * (1-cpu_fraction) if cpu and vcpu else None,
            'memory_used_gib_seconds_estimated': memory_gib * seconds * memory_fraction if memory and memory_gib else None,
            'estimation_method': 'window_mean_times_duration',
            'quality': 'estimated' if cpu or memory else 'missing',
        })
    return {'schema_version': '1.0', 'experiment_id': record['experiment_id'],
            'run_id': record['run_id'], 'window': contract['window'],
            'duration_seconds': seconds, 'instances': instances,
            'cost_unit': 'computational_only', 'monetary_cost': None,
            'limitations': ['Mean-times-duration is an estimate, not an exact integral.',
                            'Resource roles must not be combined without attribution.',
                            'Idle CPU is not automatically removable capacity.',
                            'No infrastructure pricing or billing is inferred.']}


def main():
    from src.agent.official_integration import build_records
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-root', default='.infravita/evidence/exp001')
    parser.add_argument('--output', default='.infravita/reports/computational_cost_v1.json')
    parser.add_argument('--inventory', help='Optional JSON mapping instance IDs to vcpu and memory_gib')
    args = parser.parse_args()
    inventory = json.loads(Path(args.inventory).read_text(encoding='utf-8')) if args.inventory else {}
    if not isinstance(inventory, dict):
        raise ValueError('Inventory must be a JSON object')
    results = [calculate(r, inventory) for r in build_records(Path(args.local_root))]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps({'schema_version': '1.0', 'total_runs': len(results),
                                     'runs': results}, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    print(f'COMPUTATIONAL_COST_VALIDATED runs={len(results)} output={output}')


if __name__ == '__main__':
    main()
