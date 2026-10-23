import unittest
from src.decider.decision_guardrail import evaluate


def decision(choice):
    return {'answers': {'choice_0': {'choice': choice, 'confidence': .8, 'probabilities': {choice: .8}}}}


def evidence(sla='PASS'):
    return {'experiment_id': 'EXP-001', 'run_id': 'counterfactual', 'sla_status': sla,
            'additional_metrics': {'cpu_utilization': 85, 'memory_utilization': 70},
            'efficiency': {'cpu_vcpu_seconds_per_successful_request_estimated': .3}}


class Delivery5Tests(unittest.TestCase):
    def test_failed_sla_blocks_maintain(self):
        self.assertEqual(evaluate(decision('Maintain'), evidence('FAIL'), 'computational-v1')['effective_decision'], 'Insufficient Evidence')

    def test_optimize_approved_with_valid_alternative(self):
        e = evidence(); e['optimization_alternative'] = {'validated': True, 'expected_savings_fraction': .2, 'sla_preserved': True, 'telemetry_quality': 'VALID'}
        self.assertEqual(evaluate(decision('Optimize'), e, 'computational-v1')['effective_decision'], 'Optimize')

    def test_optimize_rejected_without_alternative(self):
        self.assertEqual(evaluate(decision('Optimize'), evidence(), 'computational-v1')['effective_decision'], 'Insufficient Evidence')

    def test_scale_up_requires_multiple_signals(self):
        e = evidence('FAIL'); e['capacity_bottleneck'] = {'validated': True, 'component': 'http_server', 'telemetry_quality': 'VALID', 'signals': {'throughput_plateau': True, 'latency_or_errors_degraded': True, 'locust_generator_healthy': True, 'resource_constraint': True}}
        self.assertEqual(evaluate(decision('Scale Up'), e, 'computational-v1')['effective_decision'], 'Scale Up')
        e['capacity_bottleneck']['signals']['locust_generator_healthy'] = False
        self.assertEqual(evaluate(decision('Scale Up'), e, 'computational-v1')['effective_decision'], 'Insufficient Evidence')

    def test_evidence_hash_deterministic(self):
        a = evaluate(decision('Maintain'), evidence(), 'computational-v1')
        b = evaluate(decision('Maintain'), evidence(), 'computational-v1')
        self.assertEqual(a['evidence_sha256'], b['evidence_sha256'])
