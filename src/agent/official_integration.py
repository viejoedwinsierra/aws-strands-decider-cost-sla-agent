"""Official offline historical evidence integration for InfraVita."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.telemetry_context_v2 import format_historical_context
from src.analysis.telemetry import summarize_run
from src.analysis.telemetry_exp002 import summarize_exp002
from src.analysis.computational_cost import calculate as calculate_computational_cost
from src.analysis.efficiency import calculate as calculate_efficiency
from src.decider.evidence_adapter import build_state
from src.decider.decision_guardrail import evaluate
from src.decider.telemetry_context import prepare_evidence, format_context


def read_json(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def digest_files(paths):
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        digest.update(str(path).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def metric_count(telemetry):
    cloudwatch = sum(
        stat["sample_count"]
        for instance in telemetry["cloudwatch"].values()
        for metric in instance.values()
        for stat in metric.values()
    )
    linux = sum(
        instance["snapshot_count"]
        for instance in telemetry["linux"].values()
    )
    return {"cloudwatch_observations": cloudwatch,
            "linux_snapshots": linux}


def discover_campaigns(root):
    paths = sorted((root / "campaigns").glob("*/campaign_summary.json"))
    if not paths:
        raise ValueError("No historical campaigns found")
    return [(p.parent, read_json(p)) for p in paths]


def discover_runs(root):
    runs = {}
    for path in sorted(root.rglob("metrics_normalized.json")):
        if "campaigns" in path.parts:
            continue
        directory = path.parent
        required = [
            directory / "metrics_normalized.json",
            directory / "sla_evaluation.json",
            directory / "evidence_manifest.json",
        ]
        if not all(p.is_file() for p in required):
            continue
        metrics = read_json(required[0])
        run_id = metrics.get("run_id")
        if not run_id or run_id in runs:
            raise ValueError(f"Missing or duplicate RUN_ID: {run_id}")
        runs[run_id] = (directory, required)
    return runs




def structured_historical_context(root, campaign_dir, scenario):
    """Build historical telemetry with conservative timestamp resolution."""
    from src.analysis.telemetry_context_v2 import build_historical_context

    timestamp = scenario.get("finished_at_utc")

    if not timestamp:
        timeline_path = campaign_dir / "experiment_timeline.json"
        if timeline_path.is_file():
            timeline = read_json(timeline_path)
            if isinstance(timeline, dict):
                scenarios = timeline.get("scenarios", [])
                if isinstance(scenarios, list):
                    matches = [
                        item for item in scenarios
                        if isinstance(item, dict)
                        and item.get("run_id") == scenario.get("run_id")
                        and item.get("finished_at_utc")
                    ]
                    if len(matches) == 1:
                        timestamp = matches[0]["finished_at_utc"]

    if not timestamp:
        return {
            "as_of": None,
            "telemetry_quality": "UNKNOWN",
            "measurements": [],
            "limitations": [
                "Completion timestamp unavailable",
                "Historical telemetry not inferred",
            ],
        }

    return build_historical_context(root, timestamp)


def safe_historical_context(root, campaign_dir, scenario):
    """Resolve decision time without fabricating timestamps."""
    timestamp = scenario.get("finished_at_utc")

    if not timestamp:
        timeline_path = campaign_dir / "experiment_timeline.json"

        if timeline_path.is_file():
            timeline = read_json(timeline_path)
            matches = [
                item for item in timeline.get("scenarios", [])
                if item.get("run_id") == scenario.get("run_id")
                and item.get("finished_at_utc")
            ]

            if len(matches) == 1:
                timestamp = matches[0]["finished_at_utc"]

    if not timestamp:
        return (
            ". Historical telemetry context unavailable: "
            "scenario completion timestamp missing; "
            "no historical measurements inferred."
        )

    return format_historical_context(root, timestamp)


def summarize_compatible(campaign_dir, run_dir, run_id, experiment_id):
    """Select the historical telemetry adapter without mutating evidence."""
    if experiment_id == "EXP-002":
        return summarize_exp002(campaign_dir, run_dir, run_id)
    return summarize_run(campaign_dir, run_id)


def normalize_scenario_status(scenario):
    """Preserve recorded execution status without inventing SLA results."""
    execution = scenario.get("execution_status")
    if execution is None:
        execution = scenario.get("status", "UNKNOWN")

    sla = scenario.get("sla_status")
    if sla is None:
        sla = "NOT_EVALUATED"

    return execution, sla


def build_records(root, capacity_inventory=None):
    runs = discover_runs(root)
    records = []
    for campaign_dir, campaign in discover_campaigns(root):
        history = []  # append only after each run; never expose future scenarios
        for scenario in campaign["scenarios"]:
            run_id = scenario["run_id"]
            if run_id not in runs:
                if (scenario.get("execution_status") is None
                        and scenario.get("sla_status") == "NOT_EVALUATED"):
                    # Planned scenario skipped by the campaign safety gate.
                    # Never invent telemetry or infer a decision for it.
                    continue
                raise ValueError(f"Missing normalized evidence: {run_id}")
            directory, required = runs[run_id]
            experiment_id = read_json(required[0])["experiment_id"]
            telemetry = summarize_compatible(
                campaign_dir, directory, run_id, experiment_id
            )
            counts = metric_count(telemetry)
            if counts["cloudwatch_observations"] == 0:
                raise ValueError(f"No CloudWatch telemetry: {run_id}")
            if counts["linux_snapshots"] == 0:
                raise ValueError(f"No Linux telemetry: {run_id}")

            observations = read_json(required[0]).get("observations", {})
            base_record = {
                "experiment_id": read_json(required[0])["experiment_id"],
                "run_id": run_id,
                "telemetry": telemetry,
            }
            contract, additional_metrics = prepare_evidence(base_record, observations)
            computational_cost = calculate_computational_cost(
                {**base_record, "telemetry_contract": contract}, capacity_inventory
            )
            manifest_path = directory / "run_manifest.json"
            manifest = read_json(manifest_path) if manifest_path.is_file() else {}
            http_id = manifest.get("infrastructure", {}).get("http_instance_id")
            efficiency = calculate_efficiency(observations, computational_cost, http_id)
            # Append current scenario only after obtaining its measurements;
            # previous prefixes never include later scenarios.
            history.append({
                "scenario_id": scenario["scenario_id"],
                "run_id": run_id,
                "execution_status": normalize_scenario_status(scenario)[0],
                "sla_status": normalize_scenario_status(scenario)[1],
                "telemetry": [m for m in contract["measurements"]
                              if m["value"] is not None
                              and m["aggregation"] in ("Average.mean", "mean", "run_summary")],
            })
            historical_telemetry = structured_historical_context(
                root, campaign_dir, scenario
            )
            state = build_state(directory, telemetry_context=(
                format_context(contract, history)
                + ". Historical telemetry context (timestamp-filtered, quality not validated): "
                + json.dumps(historical_telemetry, sort_keys=True)
                + ". Computational resource consumption (estimated, not billing): "
                + json.dumps(computational_cost, sort_keys=True)
                + ". HTTP service efficiency (not monetary): "
                + json.dumps(efficiency, sort_keys=True)
            ))
            # Campaign-wide final status is metadata, not information available
            # to an earlier decision. Do not append it to model state.
            telemetry_files = list((campaign_dir / "cloudwatch").glob("*.json"))
            telemetry_files += list((campaign_dir / "linux").glob("*.jsonl"))
            telemetry_files += [
                campaign_dir / "campaign_summary.json",
                campaign_dir / "experiment_timeline.json",
            ]
            evidence_hash = digest_files(required + telemetry_files)
            records.append({
                "experiment_id": state["experiment_id"],
                "run_id": run_id,
                "scenario_id": scenario["scenario_id"],
                "execution_status": normalize_scenario_status(scenario)[0],
                "sla_status": normalize_scenario_status(scenario)[1],
                "campaign_id": campaign["campaign_id"],
                "campaign_status": campaign["status"],
                "evidence_sha256": evidence_hash,
                "telemetry_counts": counts,
                "telemetry": telemetry,
                "telemetry_contract": contract,
                "computational_cost": computational_cost,
                "efficiency": efficiency,
                "additional_metrics": additional_metrics,
                "historical_context": list(history),
                "historical_telemetry": historical_telemetry,
                "state": state,
            })
    return records


def infer(record, provider='local'):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.decider.bedrock_bridge"
            if provider == "bedrock"
            else "src.decider.local_bridge",
        ],
        input=json.dumps(record["state"]),
        text=True,
        capture_output=True,
        check=True,
        timeout=300,
    )
    raw = json.loads(result.stdout)
    guarded = evaluate(raw, {
        "experiment_id": record["experiment_id"],
        "run_id": record["run_id"],
        "additional_metrics": record["additional_metrics"],
        "efficiency": record.get("efficiency", {}),
        "sla_status": record.get("sla_status"),
    }, policy="computational-v1" if record.get("decision_policy") == "computational-v1" else "legacy")
    return {"model": raw, "guardrail": guarded}


def execute(args):
    root = Path(args.local_root).resolve()
    capacity_inventory = None
    if getattr(args, "capacity_inventory", None):
        capacity_inventory = read_json(Path(args.capacity_inventory))
    records = build_records(root, capacity_inventory)
    for record in records:
        record["decision_policy"] = getattr(args, "decision_policy", "legacy")

    if not records:
        raise ValueError("No valid historical records")

    decisions = []
    for record in records:
        result = {
            key: value
            for key, value in record.items()
            if key not in ("state", "telemetry")
        }
        result["telemetry"] = record["telemetry"]
        if args.infer:
            result.update(infer(record, provider=getattr(args, 'provider', 'local')))
        decisions.append(result)
        print(
            record["scenario_id"],
            "evidence:", record["evidence_sha256"][:12],
            "inference:", "COMPLETE" if args.infer else "SKIPPED",
            flush=True,
        )

    report = {
        "schema_version": "2.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SUCCESS",
        "model_backend": (
            "amazon-bedrock"
            if args.infer and getattr(args, "provider", "local") == "bedrock"
            else "local-strands-decider-v21" if args.infer
            else "disabled"
        ),
        "total_runs": len(decisions),
        "total_cloudwatch_observations": sum(
            d["telemetry_counts"]["cloudwatch_observations"] for d in decisions
        ),
        "total_linux_snapshots": sum(
            d["telemetry_counts"]["linux_snapshots"] for d in decisions
        ),
        "decisions": decisions,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print("OFFICIAL_RUNNER_VALIDATED", output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-root", default=".infravita/evidence/exp001")
    parser.add_argument("--output",
                        default=".infravita/reports/official_v21.json")
    parser.add_argument("--infer", action="store_true")
    parser.add_argument(
        "--provider",
        choices=("local", "bedrock"),
        default="local",
    )
    parser.add_argument("--decision-policy", choices=("legacy", "computational-v1"), default="legacy")
    parser.add_argument("--capacity-inventory", help="Optional JSON mapping instance IDs to vcpu and memory_gib")
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
