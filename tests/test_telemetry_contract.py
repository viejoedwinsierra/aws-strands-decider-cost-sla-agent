import unittest
from src.analysis.telemetry_contract import normalize_run


class TelemetryContractTests(unittest.TestCase):
    def test_values_provenance_and_missing(self):
        record = {
            "experiment_id": "EXP-001", "run_id": "test-run",
            "observations": {"latency_p95_ms": 22, "error_rate": 0.01,
                             "throughput_rps": 13, "request_count": 100},
            "telemetry": {"window": {"started_at_utc": "2026-10-22T00:00:00+00:00",
                                      "finished_at_utc": "2026-10-22T00:01:00+00:00"},
                          "cloudwatch": {"i-a": {"CPUUtilization": {"Average": {
                              "sample_count": 2, "mean": 40, "minimum": 20, "maximum": 60}}}},
                          "linux": {"i-a": {"cpu_utilization_percent": {"sample_count": 3,
                                     "mean": 44, "maximum": 72},
                                     "memory_utilization_percent": {"sample_count": 3,
                                     "mean": 53, "maximum": 65}}}}
        }
        result = normalize_run(record)
        self.assertEqual(result["run_id"], "test-run")
        values = result["measurements"]
        self.assertTrue(any(m["metric"] == "cpu_utilization" and m["value"] == 40 and m["source"] == "cloudwatch" for m in values))
        self.assertTrue(any(m["metric"] == "memory_utilization" and m["value"] == 53 and m["quality"] == "derived" for m in values))
        self.assertTrue(any(m["metric"] == "latency_p95" and m["value"] == 22 for m in values))
        self.assertTrue(any(m["metric"] == "infrastructure_cost" and m["value"] is None for m in values))
        self.assertTrue(any(m["metric"] == "capacity_headroom" and m["value"] is None for m in values))

    def test_empty_samples_do_not_become_zero(self):
        record = {"experiment_id": "EXP-001", "run_id": "r", "observations": {},
                  "telemetry": {"window": {}, "cloudwatch": {"i-a": {"CPUUtilization": {"Average": {"sample_count": 0, "mean": None}}}}, "linux": {}}}
        result = normalize_run(record)
        cpu = [m for m in result["measurements"] if m["metric"] == "cpu_utilization"]
        self.assertTrue(all(m["value"] is None and m["quality"] == "missing" for m in cpu))


if __name__ == "__main__":
    unittest.main()
