"""Offline regression checks for EXP-002 V6 and EXP-001 compatibility."""
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
EXP2 = ROOT / 'experiments/exp002_component_capacity'
EXP1 = ROOT / 'experiments/exp001_capacity'
SHARED = ROOT / 'experiments/shared'
class CampaignV6Tests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(['bash','-n',str(EXP2/'infrastructure_test/run.sh')],check=True)
    def test_exp002_offline_smoke(self):
        p=subprocess.run(['bash',str(EXP2/'infrastructure_test/run.sh'),'--dry-run','--sequence-config',str(EXP2/'config/test_sequence_smoke.yml')],capture_output=True,text=True,check=True)
        self.assertIn('EXP002_CAMPAIGN_DRY_RUN_PASS',p.stdout)
    def test_shared_cli_backward_compatibility(self):
        for script in [SHARED/'monitoring/linux_ssm.py',SHARED/'monitoring/validate_campaign.py',EXP1/'infrastructure_test/python/finalize_campaign.py']:
            p=subprocess.run([sys.executable,str(script),'--help'],capture_output=True,text=True,check=True)
            self.assertIn('EXP-001',p.stdout)
            self.assertIn('EXP-002',p.stdout)
    def test_no_aws_on_dry_run(self):
        s=(EXP2/'infrastructure_test/run.sh').read_text()
        self.assertLess(s.index('if [[ "${1:-}" == "--dry-run" ]]'),s.index('source "$CONFIG"'))
if __name__=='__main__': unittest.main()
