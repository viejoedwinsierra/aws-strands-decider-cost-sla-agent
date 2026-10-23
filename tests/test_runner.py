import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.agent.runner import discover, run_cycle
from src.analysis.history import summarize


class AgentTests(unittest.TestCase):
    def test_discover_and_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / 'exp001' / 'run_a'
            run.mkdir(parents=True)
            metrics = {'experiment_id': 'EXP-001', 'run_id': 'run_a', 'observations': {'request_count': 100, 'latency_p95_ms': 15, 'error_rate': 0.0, 'throughput_rps': 10}}
            sla = {'experiment_id': 'EXP-001', 'run_id': 'run_a', 'policy': {'max_latency_p95_ms': 100, 'max_error_rate': 0.01, 'min_throughput_rps': 4}, 'overall_status': 'PASS'}
            (run / 'metrics_normalized.json').write_text(json.dumps(metrics))
            (run / 'sla_evaluation.json').write_text(json.dumps(sla))
            (run / 'evidence_manifest.json').write_text('{}')
            records, skipped = discover(root)
            self.assertEqual(len(records), 1)
            self.assertEqual(skipped, [])
            self.assertEqual(summarize(records)['EXP-001']['median_latency_p95_ms'], 15)
            args = SimpleNamespace(local_root=str(root), sync=False, output=str(root / 'report' / 'latest.json'), decider_command=None)
            first = run_cycle(args, {'sources': []})
            second = run_cycle(args, {'sources': []})
            self.assertEqual(first['changed_runs'], 1)
            self.assertEqual(second['changed_runs'], 0)
            self.assertEqual(second['decider_status'], 'DISABLED')

    def test_mismatch_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / 'run'
            run.mkdir()
            (run / 'metrics_normalized.json').write_text(json.dumps({'experiment_id': 'EXP-001', 'run_id': 'a'}))
            (run / 'sla_evaluation.json').write_text(json.dumps({'experiment_id': 'EXP-001', 'run_id': 'b'}))
            (run / 'evidence_manifest.json').write_text('{}')
            records, skipped = discover(Path(temp))
            self.assertFalse(records)
            self.assertEqual(len(skipped), 1)


if __name__ == '__main__':
    unittest.main()
