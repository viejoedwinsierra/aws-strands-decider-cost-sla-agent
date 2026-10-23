#!/usr/bin/env python3
"""Sequential load-test campaign runner for EXP-001."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = BASE_DIR / "config" / "test_sequence.yml"
RUN_SCRIPT = BASE_DIR / "infrastructure_test" / "run_load.sh"
ANALYZE_SCRIPT = BASE_DIR / "infrastructure_test" / "analyze_results.sh"
ARCHIVE_SCRIPT = BASE_DIR / "infrastructure_test" / "archive_evidence.sh"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("YAML root must be a mapping")

    if config.get("experiment_id") != "EXP-001":
        raise ValueError("Expected experiment_id: EXP-001")

    execution = config.get("execution", {})
    if not isinstance(execution, dict):
        raise ValueError("execution must be a mapping")
    if execution.get("mode") != "sequential":
        raise ValueError("Only sequential mode is supported")
    if not isinstance(execution.get("stop_on_failure"), bool):
        raise ValueError("stop_on_failure must be boolean")

    cooldown = execution.get("cooldown_seconds", 0)
    if type(cooldown) not in (int, float) or cooldown < 0:
        raise ValueError("cooldown_seconds must be nonnegative")

    scenarios = config.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("At least one scenario is required")

    seen = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("Each scenario must be a mapping")

        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", scenario_id
        ):
            raise ValueError(f"Invalid scenario ID: {scenario_id}")

        if scenario_id in seen:
            raise ValueError(f"Duplicate scenario ID: {scenario_id}")
        seen.add(scenario_id)

        users = scenario.get("users")
        spawn_rate = scenario.get("spawn_rate")
        duration = scenario.get("duration")

        if type(users) is not int or users <= 0:
            raise ValueError(f"{scenario_id}: users must be positive integer")

        if type(spawn_rate) not in (int, float) or spawn_rate <= 0:
            raise ValueError(f"{scenario_id}: spawn_rate must be positive")

        if not isinstance(duration, str) or not re.fullmatch(
            r"[1-9][0-9]*s", duration
        ):
            raise ValueError(f"{scenario_id}: duration must be like 60s")

    return execution, scenarios


def save_summary(path, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--campaign-id", help="Campaign ID provided by the orchestration shell")
    parser.add_argument(
        "--scenarios",
        nargs="+",
        metavar="SCENARIO_ID",
        help="Run only selected scenario IDs from the YAML",
    )
    args = parser.parse_args()

    try:
        with args.config.open(encoding="utf-8") as file:
            config = yaml.safe_load(file)
        execution, scenarios = validate_config(config)

        if args.scenarios:
            requested = set(args.scenarios)
            available = {scenario["id"] for scenario in scenarios}
            unknown = requested - available

            if unknown:
                raise ValueError(
                    "Unknown scenario IDs: " + ", ".join(sorted(unknown))
                )

            scenarios = [
                scenario
                for scenario in scenarios
                if scenario["id"] in requested
            ]

    except (OSError, yaml.YAMLError, ValueError) as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    campaign_id = args.campaign_id or ("exp001_" + datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    ))
    if not re.fullmatch(r"exp001_[0-9]{8}T[0-9]{6}[0-9]+Z", campaign_id):
        print("CONFIG_ERROR: Invalid campaign ID", file=sys.stderr)
        return 2
    campaign_dir = BASE_DIR / "results" / "campaigns" / campaign_id
    summary_path = campaign_dir / "campaign_summary.json"

    summary = {
        "schema_version": "1.0",
        "experiment_id": "EXP-001",
        "campaign_id": campaign_id,
        "started_at_utc": utc_now(),
        "finished_at_utc": None,
        "status": "PLANNED" if args.dry_run else "RUNNING",
        "dry_run": args.dry_run,
        "selected_scenario_ids": [s["id"] for s in scenarios],
        "scenarios": [],
    }

    print(f"CAMPAIGN_ID: {campaign_id}")
    print(f"MODE: {'DRY_RUN' if args.dry_run else 'EXECUTE'}")

    # Register the complete execution plan before starting any scenario.
    for scenario in scenarios:
        scenario_id = scenario["id"]
        run_id = f"{campaign_id}_{scenario_id.replace('-', '')}_A01"

        summary["scenarios"].append({
            "scenario_id": scenario_id,
            "run_id": run_id,
            "users": scenario["users"],
            "spawn_rate": scenario["spawn_rate"],
            "duration": scenario["duration"],
            "status": "PLANNED" if args.dry_run else "PENDING",
            "sla_status": "NOT_EVALUATED",
            "sla_checks": None,
            "evidence_status": "NOT_AVAILABLE",
            "evidence_missing_files": [],
            "exit_code": None,
            "started_at_utc": None,
            "finished_at_utc": None,
            "local_evidence": str(BASE_DIR / "results" / run_id),
        })

    failed = False
    interrupted = False

    if not args.dry_run:
        save_summary(summary_path, summary)

    try:
        for index, record in enumerate(summary["scenarios"]):
            scenario_id = record["scenario_id"]
            run_id = record["run_id"]

            print(
                f"\n[{index + 1}/{len(scenarios)}] {scenario_id} "
                f"users={record['users']} "
                f"spawn={record['spawn_rate']} "
                f"duration={record['duration']}"
            )
            print(f"RUN_ID: {run_id}", flush=True)

            if args.dry_run:
                continue

            env = os.environ.copy()
            env.update({
                "RUN_ID": run_id,
                "USERS": str(record["users"]),
                "SPAWN_RATE": str(record["spawn_rate"]),
                "DURATION": record["duration"],
            })

            record["status"] = "RUNNING"
            record["started_at_utc"] = utc_now()
            save_summary(summary_path, summary)

            # Preserve load errors while analyzing any successfully collected CSV.
            load_result = subprocess.run(["bash", str(RUN_SCRIPT)], env=env)
            load_exit_code = load_result.returncode
            record["load_exit_code"] = load_exit_code

            stats_path = BASE_DIR / "results" / run_id / "exp001_stats.csv"
            manifest_path = BASE_DIR / "results" / run_id / "run_manifest.json"
            analysis_exit_code = None
            archive_exit_code = None
            if stats_path.is_file() and stats_path.stat().st_size > 0 and manifest_path.is_file():
                analysis_exit_code = subprocess.run(
                    ["bash", str(ANALYZE_SCRIPT), run_id], env=env
                ).returncode
                if analysis_exit_code:
                    print(f"ANALYSIS_FAILED: {run_id} exit={analysis_exit_code}", flush=True)
            else:
                print(f"ANALYSIS_SKIPPED_MISSING_EVIDENCE: {run_id}", flush=True)

            # Preserve the original failure while attempting mandatory S3 archival.
            if manifest_path.is_file():
                archive_exit_code = subprocess.run(
                    ["bash", str(ARCHIVE_SCRIPT), run_id], env=env
                ).returncode
                if archive_exit_code:
                    print(f"ARCHIVE_FAILED: {run_id} exit={archive_exit_code}", flush=True)

            record["analysis_exit_code"] = analysis_exit_code
            record["archive_exit_code"] = archive_exit_code
            record["exit_code"] = (
                load_exit_code if load_exit_code != 0
                else analysis_exit_code if analysis_exit_code not in (None, 0)
                else archive_exit_code if archive_exit_code not in (None, 0)
                else 0 if analysis_exit_code == 0 and archive_exit_code == 0
                else 1
            )
            record["finished_at_utc"] = utc_now()

            sla_path = BASE_DIR / "results" / run_id / "sla_evaluation.json"
            if sla_path.is_file():
                try:
                    with sla_path.open(encoding="utf-8") as file:
                        sla = json.load(file)

                    if sla.get("run_id") != run_id:
                        raise ValueError("SLA run_id does not match scenario")

                    if sla.get("overall_status") not in (
                        "PASS", "FAIL", "INSUFFICIENT_DATA"
                    ):
                        raise ValueError("Invalid SLA overall_status")

                    record["sla_status"] = sla["overall_status"]
                    record["sla_checks"] = sla.get("checks")
                except (OSError, ValueError, TypeError) as error:
                    record["sla_status"] = "INVALID_EVIDENCE"
                    record["sla_error"] = str(error)

            evidence_path = (
                BASE_DIR / "results" / run_id / "evidence_manifest.json"
            )
            if evidence_path.is_file():
                try:
                    with evidence_path.open(encoding="utf-8") as file:
                        evidence = json.load(file)

                    if evidence.get("run_id") != run_id:
                        raise ValueError("Evidence run_id does not match scenario")

                    evidence_status = evidence.get("archive_status")
                    missing_files = evidence.get("missing_files")

                    if evidence_status not in ("COMPLETE", "PARTIAL"):
                        raise ValueError("Invalid evidence archive_status")
                    if not isinstance(missing_files, list) or not all(
                        isinstance(name, str) for name in missing_files
                    ):
                        raise ValueError("Invalid evidence missing_files")
                    if evidence_status == "COMPLETE" and missing_files:
                        raise ValueError("COMPLETE archive has missing files")

                    record["evidence_status"] = evidence_status
                    record["evidence_missing_files"] = missing_files
                except (OSError, ValueError, TypeError) as error:
                    record["evidence_status"] = "INVALID"
                    record["evidence_error"] = str(error)

            # Keep technical execution separate from evidence validation.
            record["execution_status"] = (
                "COMPLETED" if load_exit_code == 0 else "FAILED"
            )

            valid_sla = record["sla_status"] in (
                "PASS", "FAIL", "INSUFFICIENT_DATA"
            )
            # CloudWatch and campaign timeline are deferred by design.
            # Phase 1 only requires successful individual load/SLA/archive.
            valid_evidence = record["evidence_status"] in ("COMPLETE", "PARTIAL")

            record["validation_status"] = (
                "PASS" if valid_sla and valid_evidence else "FAILED"
            )

            record["status"] = (
                "COMPLETED"
                if record["exit_code"] == 0 and valid_sla and valid_evidence
                else "FAILED"
            )

            # Fail closed between stress increments; retain all partial artifacts.
            if execution.get("safety_gate"):
                reasons = []
                if record["sla_status"] != "PASS":
                    reasons.append("sla_not_pass")
                if record["evidence_status"] != "COMPLETE":
                    reasons.append("evidence_not_complete")
                if record["exit_code"] != 0:
                    reasons.append("execution_or_archive_failed")
                record["safety_gate"] = {"approved": not reasons, "reasons": reasons}
                if reasons:
                    record["status"] = "FAILED"
                    failed = True
                    print("STRESS_SAFETY_STOP: " + ",".join(reasons), flush=True)
            save_summary(summary_path, summary)

            if record["status"] == "FAILED":
                failed = True
                if execution["stop_on_failure"]:
                    print("STOP_ON_FAILURE: remaining scenarios skipped")
                    break

            if index < len(scenarios) - 1:
                cooldown = execution.get("cooldown_seconds", 0)
                if cooldown:
                    print(f"COOLDOWN: {cooldown}s", flush=True)
                    time.sleep(cooldown)

    except KeyboardInterrupt:
        interrupted = True
        failed = True
        print("\nCAMPAIGN_INTERRUPTED", file=sys.stderr)

    finally:
        if not args.dry_run:
            for record in summary["scenarios"]:
                if record["status"] == "RUNNING":
                    record["status"] = "INTERRUPTED"
                elif record["status"] == "PENDING":
                    record["status"] = "SKIPPED"

            summary["finished_at_utc"] = utc_now()
            summary["status"] = (
                "INTERRUPTED" if interrupted
                else "FAILED" if failed
                else "LOAD_COMPLETED"
            )
            save_summary(summary_path, summary)
            print(f"\nCAMPAIGN_STATUS: {summary['status']}")
            print(f"CAMPAIGN_SUMMARY: {summary_path}")
        else:
            print("\nDRY_RUN_COMPLETED: no AWS commands executed")

    return 130 if interrupted else 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
