"""Delivery 1: local/S3 compatibility, without live AWS calls."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.agent.runner import load_source_config, resolve_source, run_cycle


class EvidenceSourcesTests(unittest.TestCase):
    def args(self, **changes):
        values = dict(source=None, sync=False, config="missing.yaml", local_root="/tmp/unused",
                      output="/tmp/unused-report.json", profile="test", region="us-east-1",
                      decider_command=None)
        values.update(changes)
        return SimpleNamespace(**values)

    def test_default_local_ignores_missing_s3_config(self):
        args = self.args()
        self.assertEqual(resolve_source(args), "local")
        self.assertIsNone(load_source_config(args))

    def test_legacy_sync_preserved(self):
        self.assertEqual(resolve_source(self.args(sync=True)), "s3")
        self.assertEqual(resolve_source(self.args(source="s3")), "s3")

    def test_conflicting_flags_fail(self):
        with self.assertRaisesRegex(ValueError, "conflicts"):
            resolve_source(self.args(sync=True, source="local"))

    def test_s3_configuration_still_validates_bucket(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sources.yaml"
            path.write_text('sources:\n  - id: exp001\n    uri: s3://${EVIDENCE_BUCKET}/evidence/\n')
            args = self.args(source="s3", config=str(path))
            with patch.dict(os.environ, {"EVIDENCE_BUCKET": ""}):
                with self.assertRaisesRegex(ValueError, "EVIDENCE_BUCKET"):
                    load_source_config(args)
            with patch.dict(os.environ, {"EVIDENCE_BUCKET": "example-bucket"}):
                config = load_source_config(args)
            self.assertEqual(config["sources"][0]["uri"], "s3://example-bucket/evidence/")

    def test_s3_uses_original_synchronizer(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args(source="s3", local_root=temp, output=str(Path(temp)/"report.json"))
            config = {"sources": [{"id": "exp001", "uri": "s3://example/evidence/"}]}
            with patch("src.agent.runner.sync_sources") as sync:
                report = run_cycle(args, config)
            sync.assert_called_once_with(config["sources"], Path(temp).resolve(), "test", "us-east-1")
            self.assertEqual(report["total_runs"], 0)

    def test_cli_local_without_bucket(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ)
            env.pop("EVIDENCE_BUCKET", None)
            result = subprocess.run([sys.executable, "-m", "src.agent.runner", "--source", "local",
                                     "--local-root", temp, "--output", str(Path(temp)/"report.json")],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["total_runs"], 0)


if __name__ == "__main__":
    unittest.main()
