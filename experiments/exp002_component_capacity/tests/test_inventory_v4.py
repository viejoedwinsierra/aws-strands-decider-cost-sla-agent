import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roles', ROOT/'infrastructure_test/python/resolve_instance_roles.py')
roles=importlib.util.module_from_spec(spec);spec.loader.exec_module(roles)
class RoleTests(unittest.TestCase):
 def test_resolve(self):
  data={'experiment_id':'EXP-002','instances':[{'role':'workload-server','state':'running','instance_id':'i-111'}, {'role':'load-generator','state':'running','instance_id':'i-222'}]}
  self.assertEqual(roles.resolve(data),('i-111','i-222'))
 def test_wrong_experiment(self):
  with self.assertRaises(ValueError): roles.resolve({'experiment_id':'EXP-001','instances':[]})
 def test_duplicate_role(self):
  with self.assertRaises(ValueError): roles.resolve({'experiment_id':'EXP-002','instances':[{'role':'workload-server','state':'running','instance_id':'i-1'},{'role':'workload-server','state':'running','instance_id':'i-2'}]})
