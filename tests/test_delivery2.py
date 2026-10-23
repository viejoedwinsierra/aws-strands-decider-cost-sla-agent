"""Delivery 2 regression tests: measured evidence, temporal isolation, guardrails."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from src.decider.telemetry_context import prepare_evidence, format_context
from src.decider.decision_guardrail import evaluate
from src.decider.evidence_adapter import build_state
from src.agent.official_integration import infer, build_records


def fixture():
    return {
        "experiment_id": "EXP-001", "run_id": "run-a",
        "telemetry": {
            "window": {"started_at_utc": "2026-10-22T00:00:00+00:00", "finished_at_utc": "2026-10-22T00:01:00+00:00"},
            "cloudwatch": {"i-a": {"CPUUtilization": {"Average": {
                "sample_count": 2, "mean": 81, "minimum": 75, "maximum": 90}}}},
            "linux": {"i-a": {"snapshot_count": 3,
                "cpu_utilization_percent": {"sample_count": 3, "mean": 82, "maximum": 91},
                "memory_utilization_percent": {"sample_count": 3, "mean": 67, "maximum": 78}}},
        },
    }


class Delivery2Tests(unittest.TestCase):
    def test_model_receives_numeric_values_and_provenance(self):
        contract, extra = prepare_evidence(fixture(), {
            "latency_p95_ms": 123, "throughput_rps": 22, "error_rate": 0.02, "request_count": 99})
        state = format_context(contract, [{"run_id": "run-a"}])
        self.assertIn('"value": 81', state)
        self.assertIn('"value": 123', state)
        self.assertIn('"source": "cloudwatch"', state)
        self.assertIn('"source": "linux_ssm"', state)
        self.assertIn('"unit": "ms"', state)
        self.assertEqual(extra["cpu_utilization"], 81)
        self.assertEqual(extra["memory_utilization"], 67)
        self.assertIsNone(extra["capacity_headroom"])
        self.assertIsNone(extra["infrastructure_cost"])

    def test_guardrail_receives_actual_available_metrics(self):
        _, extra = prepare_evidence(fixture(), {})
        decision = {"answers": {"choice_0": {"choice": "Optimize", "confidence": .8,
                          "probabilities": {"Optimize": .7}}}}
        with patch("src.agent.official_integration.subprocess.run", return_value=Mock(stdout=json.dumps(decision))) as call:
            result = infer({"experiment_id": "EXP-001", "run_id": "run-a",
                            "state": {"state": "x", "question": "q", "options": ["Optimize"]},
                            "additional_metrics": extra})
        self.assertTrue(call.called)
        self.assertEqual(result["guardrail"]["missing_evidence"],
                         ["capacity_headroom", "infrastructure_cost"])
        self.assertEqual(result["guardrail"]["effective_decision"], "Insufficient Evidence")

    def test_empty_cpu_not_fabricated(self):
        rec = fixture()
        rec["telemetry"]["cloudwatch"]["i-a"]["CPUUtilization"]["Average"] = {
            "sample_count": 0, "mean": None, "minimum": None, "maximum": None}
        rec["telemetry"]["linux"]["i-a"]["cpu_utilization_percent"] = {"sample_count": 0}
        _, extra = prepare_evidence(rec, {})
        self.assertIsNone(extra["cpu_utilization"])

    def test_adapter_removes_false_unavailable_claim(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            (directory / "metrics_normalized.json").write_text(json.dumps({
                "experiment_id": "EXP-001", "run_id": "r", "observations": {
                    "request_count": 100, "latency_p95_ms": 20,
                    "error_rate": .01, "throughput_rps": 4}}))
            (directory / "sla_evaluation.json").write_text(json.dumps({
                "experiment_id": "EXP-001", "run_id": "r", "overall_status": "PASS",
                "policy": {"max_latency_p95_ms": 200, "max_error_rate": .05,
                           "min_throughput_rps": 1}}))
            result = build_state(directory, telemetry_context="CPU 81 percent measured")
            self.assertIn("CPU 81 percent measured", result["state"])
            self.assertNotIn("CPU utilization, memory utilization", result["state"])

    def test_history_prefix_never_contains_future_scenario(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            campaign = root / "campaigns" / "c1"
            campaign.mkdir(parents=True)
            scenarios = []
            for i in range(3):
                rid = f"run-{i}"
                scenarios.append({"run_id": rid, "scenario_id": f"LB-0{i+1}",
                                  "execution_status": "SUCCESS", "sla_status": "PASS"})
                run_dir = root / rid
                run_dir.mkdir()
                (run_dir / "metrics_normalized.json").write_text(json.dumps({
                    "experiment_id": "EXP-001", "run_id": rid, "observations": {
                        "request_count": 10, "latency_p95_ms": 20,
                        "error_rate": 0, "throughput_rps": 3}}))
                (run_dir / "sla_evaluation.json").write_text(json.dumps({
                    "experiment_id": "EXP-001", "run_id": rid, "overall_status": "PASS",
                    "policy": {"max_latency_p95_ms": 200, "max_error_rate": .05,
                               "min_throughput_rps": 1}}))
                (run_dir / "evidence_manifest.json").write_text('{}')
            (campaign / "campaign_summary.json").write_text(json.dumps({
                "campaign_id": "c1", "status": "FAILED", "scenarios": scenarios}))
            (campaign / "experiment_timeline.json").write_text('{}')
            with patch("src.agent.official_integration.summarize_run", return_value=fixture()["telemetry"]):
                records = build_records(root)
            self.assertEqual([len(r["historical_context"]) for r in records], [1, 2, 3])
            self.assertNotIn("run-2", records[0]["state"]["state"])
            self.assertNotIn("Campaign status: FAILED", records[0]["state"]["state"])
            self.assertIn("run-2", records[2]["state"]["state"])


if __name__ == "__main__":
    unittest.main()
