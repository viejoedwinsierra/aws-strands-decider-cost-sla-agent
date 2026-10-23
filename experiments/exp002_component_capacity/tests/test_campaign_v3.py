import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('exp002_sequence', ROOT/'infrastructure_test/python/sequence_runner.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class CampaignTests(unittest.TestCase):
    def test_smoke(self):
        self.assertEqual(MOD.parse_sequence(ROOT/'config/test_sequence_smoke.yml')['scenarios'][0]['users'],3)
    def test_default(self):
        self.assertEqual(len(MOD.parse_sequence(ROOT/'config/test_sequence.yml')['scenarios']),3)
    def test_wrong_experiment(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'wrong.yml'
            path.write_text('experiment_id: EXP-001\nscenarios: []\n')
            with self.assertRaises(ValueError): MOD.parse_sequence(path)
