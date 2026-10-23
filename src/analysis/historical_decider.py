"""Offline historical inference over an existing EXP-001 campaign."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from src.analysis.telemetry import summarize_run
from src.decider.evidence_adapter import build_state
from src.decider.decision_guardrail import evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-root", default=".infravita/evidence/exp001")
    parser.add_argument(
        "--output",
        default=".infravita/reports/historical_decider_v21.json"
    )
    args = parser.parse_args()

    root = Path(args.local_root)
    campaigns = sorted(p for p in (root / "campaigns").iterdir() if p.is_dir())
    if len(campaigns) != 1:
        raise ValueError("Se esperaba exactamente una campaña")

    campaign = campaigns[0]
    summary = json.loads((campaign / "campaign_summary.json").read_text())
    if len(summary["scenarios"]) != 7:
        raise ValueError("Se esperaban siete escenarios")

    states = []
    for scenario in summary["scenarios"]:
        run_id = scenario["run_id"]
        matches = [
            p.parent for p in root.rglob("metrics_normalized.json")
            if json.loads(p.read_text()).get("run_id") == run_id
        ]
        if len(matches) != 1:
            raise ValueError(f"Evidencia ambigua: {run_id}")

        state = build_state(matches[0])
        telemetry = summarize_run(campaign, run_id)

        state["state"] += (
            f" Campaign execution status: {summary['status']}."
            f" Scenario execution status: {scenario['execution_status']}."
            f" Scenario SLA status: {scenario['sla_status']}."
            f" CloudWatch telemetry: {json.dumps(telemetry['cloudwatch'])}."
            f" Linux telemetry: {json.dumps(telemetry['linux'])}."
            " Capacity headroom and infrastructure cost are unverified."
        )
        states.append((scenario, state, telemetry))

    # Every inference sees a compact overview of the complete campaign.
    context = [
        {
            "scenario": scenario["scenario_id"],
            "run_id": scenario["run_id"],
            "execution_status": scenario["execution_status"],
            "sla_status": scenario["sla_status"],
        }
        for scenario, _, _ in states
    ]

    decisions = []
    for scenario, state, telemetry in states:
        payload = dict(state)
        payload["state"] += " Historical campaign context: " + json.dumps(context)

        result = subprocess.run(
            [sys.executable, "-m", "src.decider.local_bridge"],
            input=json.dumps(payload),
            capture_output=True, text=True,
            timeout=300, check=True,
        )
        raw = json.loads(result.stdout)

        # Conservative guardrail: no fabricated cost/headroom.
        guarded = evaluate(raw, {
            "experiment_id": state["experiment_id"],
            "run_id": state["run_id"],
            "additional_metrics": {
                "cpu_utilization": None,
                "memory_utilization": None,
                "capacity_headroom": None,
                "infrastructure_cost": None,
            },
        })

        decisions.append({
            "scenario_id": scenario["scenario_id"],
            "run_id": scenario["run_id"],
            "execution_status": scenario["execution_status"],
            "sla_status": scenario["sla_status"],
            "telemetry": telemetry,
            "model": raw,
            "guardrail": guarded,
        })
        print(
            scenario["scenario_id"],
            guarded["model_decision"],
            "effective:", guarded["effective_decision"],
            flush=True,
        )

    report = {
        "schema_version": "2.1",
        "campaign_id": summary["campaign_id"],
        "campaign_status": summary["status"],
        "model_backend": "local-strands-decider-v21",
        "total_runs": len(decisions),
        "decisions": decisions,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print("HISTORICAL_DECIDER_SUCCESS", output)


if __name__ == "__main__":
    main()
