#!/usr/bin/env python3
import pathlib, subprocess, tempfile, os, shutil, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class V5Tests(unittest.TestCase):
    def test_shell_syntax(self):
        for p in (ROOT/'infrastructure').glob('*.sh'):
            subprocess.run(['bash','-n',str(p)],check=True)
    def test_components_reused(self):
        d=(ROOT/'infrastructure/deploy.sh').read_text()
        for name in ('create_bucket.sh','prepare_dependencies.sh','provision.sh','deploy_postgresql.sh','deploy_fastapi.sh','deploy_locust.sh','configure_network.sh','verify_all.sh'):
            self.assertIn(name,d)
        v=(ROOT/'infrastructure/verify_all.sh').read_text()
        for name in ('verify_security.sh','verify.sh','verify_locust.sh','verify_network.sh'):
            self.assertIn(name,v)
    def test_bucket_fail_closed(self):
        b=(ROOT/'infrastructure/create_bucket.sh').read_text()
        self.assertIn('Refusing to create a replacement',b)
        self.assertNotIn('Preserving historical reference and creating a new bucket',b)
    def test_modes(self):
        b=(ROOT/'infrastructure/bootstrap_all.sh').read_text()
        for name in ('deploy|resume','verify)','run)'):
            self.assertIn(name,b)
if __name__=='__main__': unittest.main()
