"""Computational decision policy and efficiency regression tests."""
import unittest
from src.analysis.efficiency import calculate
from src.decider.decision_guardrail import evaluate


def decision(choice):
    return {'answers': {'choice_0': {'choice': choice, 'confidence': 0.8,
            'probabilities': {choice: 0.75}}}}


def evidence(sla='PASS', cpu=20, memory=40):
    return {'experiment_id': 'EXP-001', 'run_id': 'r1', 'sla_status': sla,
            'additional_metrics': {'cpu_utilization': cpu, 'memory_utilization': memory,
                                   'capacity_headroom': None, 'infrastructure_cost': None},
            'efficiency': {'cpu_vcpu_seconds_per_successful_request_estimated': 0.1}}


class Delivery4Tests(unittest.TestCase):
    def test_efficiency_excludes_locust(self):
        cost = {'instances': [
            {'instance_id': 'http', 'cpu_used_vcpu_seconds_estimated': 20,
             'memory_used_gib_seconds_estimated': 10},
            {'instance_id': 'locust', 'cpu_used_vcpu_seconds_estimated': 900,
             'memory_used_gib_seconds_estimated': 900}]}
        result = calculate({'request_count': 100, 'error_rate': 0.1,
                            'latency_p95_ms': 80, 'throughput_rps': 5}, cost, 'http')
        self.assertAlmostEqual(result['successful_requests_estimated'], 90)
        self.assertAlmostEqual(result['cpu_vcpu_seconds_per_successful_request_estimated'], 20 / 90)
        self.assertEqual(result['attribution'], 'http_service_only')

    def test_unknown_http_role_never_fabricated(self):
        result = calculate({'request_count': 100, 'error_rate': 0},
                           {'instances': [{'instance_id': 'locust', 'cpu_used_vcpu_seconds_estimated': 2}]})
        self.assertIsNone(result['cpu_vcpu_seconds_per_successful_request_estimated'])

    def test_zero_success_never_divides(self):
        result = calculate({'request_count': 100, 'error_rate': 1},
                           {'instances': [{'instance_id': 'http', 'cpu_used_vcpu_seconds_estimated': 2}]}, 'http')
        self.assertIsNone(result['cpu_vcpu_seconds_per_successful_request_estimated'])

    def test_invalid_error_rate_not_assumed(self):
        result = calculate({'request_count': 100, 'error_rate': 1.3}, {'instances': []}, 'http')
        self.assertIsNone(result['successful_requests_estimated'])

    def test_maintain_can_pass_without_money(self):
        result = evaluate(decision('Maintain'), evidence(), policy='computational-v1')
        self.assertEqual(result['effective_decision'], 'Maintain')
        self.assertEqual(result['policy_version'], 'computational-v1')

    def test_maintain_blocked_when_sla_fails(self):
        result = evaluate(decision("Maintain"), evidence(sla="FAIL"), policy="computational-v1")
        self.assertEqual(result["effective_decision"], "Insufficient Evidence")

    def test_missing_cpu_blocks_maintain(self):
        result = evaluate(decision('Maintain'), evidence(cpu=None), policy='computational-v1')
        self.assertIn('cpu_utilization', result['missing_evidence'])

    def test_optimize_requires_validated_alternative(self):
        result = evaluate(decision('Optimize'), evidence(), policy='computational-v1')
        self.assertEqual(result['effective_decision'], 'Insufficient Evidence')
        self.assertIn('validated_optimization_alternative', result['missing_evidence'])

    def test_scale_up_requires_bottleneck_even_if_sla_failed(self):
        result = evaluate(decision('Scale Up'), evidence(sla='FAIL'), policy='computational-v1')
        self.assertIn('validated_capacity_bottleneck', result['missing_evidence'])

    def test_legacy_unchanged(self):
        result = evaluate(decision('Maintain'), evidence())
        self.assertEqual(result['missing_evidence'], ['capacity_headroom', 'infrastructure_cost'])
        self.assertEqual(result['policy_version'], 'experimental-v0.2')

    def test_sensitivity_to_requests_and_cpu(self):
        c = {'instances': [{'instance_id': 'http', 'cpu_used_vcpu_seconds_estimated': 50}]}
        low = calculate({'request_count': 100, 'error_rate': 0}, c, 'http')
        high = calculate({'request_count': 200, 'error_rate': 0}, c, 'http')
        self.assertGreater(low['cpu_vcpu_seconds_per_successful_request_estimated'],
                           high['cpu_vcpu_seconds_per_successful_request_estimated'])


if __name__ == '__main__':
    unittest.main()
