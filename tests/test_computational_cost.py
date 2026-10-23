import unittest
from src.analysis.computational_cost import calculate


def record(cpu=25, mem=50, samples=3):
    return {'experiment_id': 'EXP-001', 'run_id': 'r1', 'telemetry_contract': {
        'window': {'started_at_utc': '2026-10-23T00:00:00+00:00',
                   'finished_at_utc': '2026-10-23T00:01:00+00:00'},
        'measurements': [
            {'instance_id': 'i-http', 'metric': 'cpu_utilization', 'source': 'cloudwatch',
             'aggregation': 'Average.mean', 'value': cpu, 'sample_count': samples, 'quality': 'observed'},
            {'instance_id': 'i-http', 'metric': 'cpu_utilization', 'source': 'linux_ssm',
             'aggregation': 'mean', 'value': 90, 'sample_count': 4, 'quality': 'derived'},
            {'instance_id': 'i-http', 'metric': 'memory_utilization', 'source': 'linux_ssm',
             'aggregation': 'mean', 'value': mem, 'sample_count': 4, 'quality': 'derived'},
        ]}}


class ComputationalCostTests(unittest.TestCase):
    def test_without_inventory_never_invents_absolute_usage(self):
        result = calculate(record())['instances'][0]
        self.assertEqual(result['cpu_utilization_percent_seconds_proxy'], 1500)
        self.assertIsNone(result['cpu_used_vcpu_seconds_estimated'])
        self.assertIsNone(result['memory_used_gib_seconds_estimated'])

    def test_inventory_enables_explicit_estimates(self):
        result = calculate(record(), {'i-http': {'vcpu': 2, 'memory_gib': 4}})['instances'][0]
        self.assertEqual(result['cpu_used_vcpu_seconds_estimated'], 30)
        self.assertEqual(result['cpu_idle_vcpu_seconds_estimated'], 90)
        self.assertEqual(result['memory_used_gib_seconds_estimated'], 120)
        self.assertEqual(result['cpu_source'], 'cloudwatch')

    def test_missing_samples_do_not_become_zero(self):
        result = calculate(record(cpu=0, samples=0))['instances'][0]
        self.assertEqual(result['cpu_source'], 'linux_ssm')
        self.assertEqual(result['cpu_mean_percent'], 90)

    def test_missing_cpu_stays_missing(self):
        r = record()
        r['telemetry_contract']['measurements'] = [m for m in r['telemetry_contract']['measurements'] if m['metric'] != 'cpu_utilization']
        result = calculate(r, {'i-http': {'vcpu': 2}})['instances'][0]
        self.assertIsNone(result['cpu_used_vcpu_seconds_estimated'])

    def test_invalid_capacity_rejected(self):
        with self.assertRaises(ValueError):
            calculate(record(), {'i-http': {'vcpu': 0}})

    def test_invalid_duration_rejected(self):
        r = record()
        r['telemetry_contract']['window']['finished_at_utc'] = '2026-10-22T00:00:00+00:00'
        with self.assertRaises(ValueError):
            calculate(r)

    def test_monetary_cost_never_assumed(self):
        self.assertIsNone(calculate(record())['monetary_cost'])
