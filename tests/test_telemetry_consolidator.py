"""Regression tests for historical telemetry consolidation."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src.analysis.telemetry_consolidator import (
    consolidate, quality, interval,
)


class TelemetryConsolidatorTests(unittest.TestCase):

    def test_missing_samples(self):
        self.assertEqual(quality(0, 60, "cloudwatch"), "INSUFFICIENT")

    def test_single_sample_not_valid(self):
        self.assertEqual(quality(1, 60, "cloudwatch"), "PARTIAL")

    def test_multiple_samples_not_automatically_valid(self):
        self.assertEqual(quality(60, 3600, "cloudwatch"), "PARTIAL")

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            interval("2026-10-23T01:00:00Z",
                     "2026-10-23T00:00:00Z")

    def test_empty_repository(self):
        with TemporaryDirectory() as directory:
            result = consolidate(directory)
            self.assertEqual(result["total_runs"], 0)
            self.assertEqual(result["campaign_count"], 0)

    def test_real_historical_evidence_when_available(self):
        root = Path("experiments/exp001_capacity/results")
        if not (root / "campaigns").is_dir():
            self.skipTest("Local evidence not available")

        result = consolidate(root)
        self.assertEqual(result["campaign_count"], 2)
        self.assertEqual(result["total_runs"], 14)

        for campaign in result["campaigns"]:
            self.assertEqual(
                set(campaign["phases"]), {"PRE", "RUN", "POST"}
            )
            self.assertEqual(campaign["scenario_count"], 7)


if __name__ == "__main__":
    unittest.main()
