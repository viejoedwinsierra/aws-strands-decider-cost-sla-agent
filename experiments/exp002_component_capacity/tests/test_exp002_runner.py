"""Offline smoke checks for EXP-002 result normalization and SLA."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'infrastructure' / 'run_experiment.py'

class RunnerTests(unittest.TestCase):
    def test_locust_aggregated_stats_and_sla(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {
                'EVIDENCE_BUCKET': 'example-evidence', 'WORKLOAD_INSTANCE_ID': 'i-testworkload',
                'LOCUST_INSTANCE_ID': 'i-testlocust', 'LOCUST_BUNDLE_HASH': 'a'*64,
                'RUN_ID': 'exp002_test_run',
            }):
                spec=importlib.util.spec_from_file_location('exp002_runner_test', MODULE)
                module=importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.OUT=Path(tmp)
                (module.OUT/'exp002_stats.csv').write_text(
                    'Type,Name,Request Count,Failure Count,95%,Requests/s\n'
                    'Aggregated,,100,0,75,10\n')
                self.assertEqual(module.parse_stats(), 'PASS')
                data=json.loads((module.OUT/'metrics_normalized.json').read_text())
                self.assertEqual(data['experiment_id'],'EXP-002')
                self.assertEqual(data['observations']['request_count'],100)
                (module.OUT/'exp002_stats.csv').write_text(
                    'Type,Name,Request Count,Failure Count,95%,Requests/s\n'
                    'Aggregated,,100,20,1500,10\n')
                self.assertEqual(module.parse_stats(), 'FAIL')

if __name__ == '__main__':
    unittest.main()
