import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Evaluate experimental SLA for EXP-001"
)
parser.add_argument("--run-id", required=True)
args = parser.parse_args()

if not args.run_id or not all(
    c.isalnum() or c in "_-" for c in args.run_id
):
    parser.error("Invalid run-id")

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "results" / args.run_id / "metrics_normalized.json"

data = json.loads(SOURCE.read_text(encoding="utf-8"))
observations = data["observations"]

policy = {
    "max_latency_p95_ms": 100.0,
    "max_error_rate": 0.01,
    "min_throughput_rps": 4.0,
}

checks = {
    "latency_p95": {
        "observed": observations.get("latency_p95_ms"),
        "threshold": policy["max_latency_p95_ms"],
        "operator": "<=",
    },
    "error_rate": {
        "observed": observations.get("error_rate"),
        "threshold": policy["max_error_rate"],
        "operator": "<=",
    },
    "throughput": {
        "observed": observations.get("throughput_rps"),
        "threshold": policy["min_throughput_rps"],
        "operator": ">=",
    },
}

for check in checks.values():
    value = check["observed"]
    if value is None:
        check["status"] = "INSUFFICIENT_DATA"
    elif check["operator"] == "<=":
        check["status"] = "PASS" if value <= check["threshold"] else "FAIL"
    else:
        check["status"] = "PASS" if value >= check["threshold"] else "FAIL"

statuses = [check["status"] for check in checks.values()]

overall = (
    "FAIL" if "FAIL" in statuses
    else "INSUFFICIENT_DATA" if "INSUFFICIENT_DATA" in statuses
    else "PASS"
)

result = {
    "experiment_id": data["experiment_id"],
    "run_id": data["run_id"],
    "evaluation_type": "experimental_sla",
    "policy": policy,
    "checks": checks,
    "overall_status": overall,
    "interpretation": (
        "Observed metrics satisfy the experimental thresholds."
        if overall == "PASS"
        else "At least one threshold failed or data is insufficient."
    ),
}

output = SOURCE.parent / "sla_evaluation.json"
output.write_text(
    json.dumps(result, indent=2) + "\n",
    encoding="utf-8",
)

print(json.dumps(result, indent=2))
print(f"\nGenerated: {output}")
