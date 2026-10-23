"""Conservative descriptive analysis over verified local runs."""
from statistics import median


def summarize(records: list[dict]) -> dict:
    grouped = {}
    for record in records:
        grouped.setdefault(record["experiment_id"], []).append(record)
    summary = {}
    for experiment, rows in sorted(grouped.items()):
        p95 = [r["observations"].get("latency_p95_ms") for r in rows]
        p95 = [float(x) for x in p95 if isinstance(x, (int, float))]
        summary[experiment] = {
            "runs": len(rows),
            "sla_status_counts": {status: sum(r["sla_status"] == status for r in rows) for status in sorted({r["sla_status"] for r in rows})},
            "median_latency_p95_ms": median(p95) if p95 else None,
        }
    return summary
