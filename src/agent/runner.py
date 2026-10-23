"""Offline-first evidence analyzer; never installs packages or starts load tests."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.history import summarize
from src.evidence.sources import load_config
from src.evidence.synchronizer import sync_sources
from src.decider.evidence_adapter import build_state
from src.decider.decision_guardrail import evaluate


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


def discover(local_root: Path) -> tuple[list[dict], list[dict]]:
    valid, skipped = [], []
    for metrics_file in sorted(local_root.rglob("metrics_normalized.json")):
        directory = metrics_file.parent
        sla_file = directory / "sla_evaluation.json"
        manifest = directory / "evidence_manifest.json"
        if not sla_file.is_file() or not manifest.is_file():
            skipped.append({"directory": str(directory), "reason": "missing SLA or evidence manifest"})
            continue
        try:
            evidence = read_json(metrics_file)
            sla = read_json(sla_file)
            if evidence.get("experiment_id") != sla.get("experiment_id") or evidence.get("run_id") != sla.get("run_id"):
                raise ValueError("run/experiment identity mismatch")
            if not evidence.get("run_id") or not evidence.get("experiment_id"):
                raise ValueError("missing evidence identity")
            state = build_state(directory)
            digest = hashlib.sha256(metrics_file.read_bytes() + sla_file.read_bytes() + manifest.read_bytes()).hexdigest()
            valid.append({"experiment_id": evidence["experiment_id"], "run_id": evidence["run_id"], "directory": str(directory), "observations": evidence.get("observations", {}), "sla_status": sla.get("overall_status", "UNKNOWN"), "state": state, "digest": digest})
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            skipped.append({"directory": str(directory), "reason": str(exc)})
    return valid, skipped


def run_cycle(args, config: dict) -> dict:
    local_root = Path(args.local_root).resolve()
    if args.sync:
        sync_sources(config["sources"], local_root, args.profile, args.region)
    records, skipped = discover(local_root)
    checkpoint_path = Path(args.output).resolve().parent / "checkpoint.json"
    try:
        previous = read_json(checkpoint_path) if checkpoint_path.is_file() else {}
    except (ValueError, OSError):
        previous = {}
    current = {r["experiment_id"] + ":" + r["run_id"] + ":" + r["directory"]: r["digest"] for r in records}
    changed = [r for r in records if previous.get(r["experiment_id"] + ":" + r["run_id"] + ":" + r["directory"]) != r["digest"]]
    decisions = []
    errors = []
    if args.decider_command:
        for record in changed:
            try:
                result = subprocess.run(args.decider_command, input=json.dumps(record["state"]), text=True, capture_output=True, check=True, timeout=180)
                raw_decision = json.loads(result.stdout)
                guarded = evaluate(raw_decision, {"experiment_id": record["experiment_id"], "run_id": record["run_id"], "additional_metrics": record["state"].get("additional_metrics", {})})
                decisions.append({"run_id": record["run_id"], "experiment_id": record["experiment_id"], "result": guarded})
            except (subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
                errors.append({"run_id": record["run_id"], "reason": str(exc)})
    report = {"schema_version": "2.0", "generated_at": datetime.now(timezone.utc).isoformat(), "status": "PARTIAL" if skipped or errors else "SUCCESS", "total_runs": len(records), "changed_runs": len(changed), "historical_summary": summarize(records), "decider_status": "DISABLED" if not args.decider_command else ("FAILED" if errors else "SUCCESS"), "decisions": decisions, "skipped": skipped, "errors": errors, "source_directories": sorted({str(Path(r["directory"]).parent) for r in records})}
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    if not errors:
        temp_checkpoint = checkpoint_path.with_suffix(".tmp")
        temp_checkpoint.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        temp_checkpoint.replace(checkpoint_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="experiments/exp001_capacity/config/evidence_sources.yaml")
    parser.add_argument("--local-root", default=".infravita/evidence")
    parser.add_argument("--output", default=".infravita/reports/latest.json")
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE", "academy-sandbox"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--decider-command", nargs="+", help="Verified real Decider CLI accepting state JSON on stdin and returning model decision JSON on stdout")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    while True:
        try:
            report = run_cycle(args, config)
            print(json.dumps({k: report[k] for k in ("status", "total_runs", "changed_runs", "decider_status")}), flush=True)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            print(f"ANALYSIS_ERROR: {exc}", file=sys.stderr, flush=True)
            if not args.watch:
                raise SystemExit(1) from exc
        if not args.watch:
            if report["status"] != "SUCCESS":
                raise SystemExit(2)
            break
        time.sleep(config["interval_seconds"])


if __name__ == "__main__":
    main()
