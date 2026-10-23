import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v64sequence', ROOT / 'infrastructure_test/python/sequence_runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class V64Contract(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'sequence.yml'
            p.write_text(text)
            return module.parse_sequence(p)

    def test_crud_yaml(self):
        data = module.parse_sequence(ROOT / 'config/test_sequence_crud_v64.yml')
        self.assertEqual([x['id'] for x in data['scenarios']], ['DB-SMOKE', 'DB-CRUD'])
        self.assertFalse(data['execution']['stop_on_failure'])
        self.assertEqual({x['method'] for x in data['scenarios'][1]['http']['operations']}, {'GET','POST','PUT','PATCH','DELETE'})

    def test_invalid_method(self):
        text = (ROOT / 'config/test_sequence_crud_v64.yml').read_text().replace('method: DELETE', 'method: DROP')
        with self.assertRaises(ValueError):
            self.parse(text)

    def test_invalid_sla(self):
        text = (ROOT / 'config/test_sequence_crud_v64.yml').read_text().replace('max_error_rate: 0.01', 'max_error_rate: 2')
        with self.assertRaises(ValueError):
            self.parse(text)

    def test_legacy(self):
        self.assertEqual(len(module.parse_sequence(ROOT / 'config/test_sequence_smoke.yml')['scenarios']), 1)

if __name__ == '__main__':
    unittest.main()
