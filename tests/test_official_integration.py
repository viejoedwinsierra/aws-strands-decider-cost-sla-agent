"""InfraVita official historical integration tests."""
import unittest
from pathlib import Path

from src.agent.official_integration import (
    build_records,
    discover_campaigns,
    metric_count,
)


ROOT = Path(".infravita/evidence/exp001")


@unittest.skipUnless(ROOT.is_dir(), "Historical evidence not available")
class OfficialIntegrationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.records = build_records(ROOT)

    def test_campaign_available(self):
        self.assertGreaterEqual(len(discover_campaigns(ROOT)), 1)

    def test_seven_scenarios(self):
        self.assertEqual(len(self.records), 7)

    def test_multisource_coverage(self):
        for record in self.records:
            counts = metric_count(record["telemetry"])
            self.assertGreater(counts["cloudwatch_observations"], 0)
            self.assertGreater(counts["linux_snapshots"], 0)

    def test_execution_and_sla_distinction(self):
        failed = [
            r for r in self.records
            if r["execution_status"] == "FAILED"
        ]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["scenario_id"], "LB-07")
        self.assertEqual(failed[0]["sla_status"], "PASS")

    def test_evidence_integrity(self):
        for record in self.records:
            self.assertEqual(len(record["evidence_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
