import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import torch
from strands_decider.infer import load_engine
from strands_decider.schema import ChoiceQuestion

CHECKPOINT = "StrandsAgents/strands-decider-2B-hobson-v21"
BASE_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = BASE_DIR / "scenarios.json"
RESULTS_DIR = BASE_DIR / "results"

TOOLS = {
    "analyze_capacity": "Analyze resource utilization, capacity constraints and workload headroom.",
    "evaluate_sla_risk": "Evaluate service-level objective violations, reliability and SLA risk.",
    "estimate_cost_efficiency": "Compare technological costs, economic efficiency and performance trade-offs.",
}

QUESTION_ID = "tool_selection"


def macro_f1(results):
    scores = []

    for tool in TOOLS:
        tp = sum(
            r["expected_tool"] == tool and r["selected_tool"] == tool
            for r in results
        )
        fp = sum(
            r["expected_tool"] != tool and r["selected_tool"] == tool
            for r in results
        )
        fn = sum(
            r["expected_tool"] == tool and r["selected_tool"] != tool
            for r in results
        )

        denominator = 2 * tp + fp + fn
        scores.append(2 * tp / denominator if denominator else 0.0)

    return sum(scores) / len(scores)


def main():
    scenarios = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not scenarios:
        raise ValueError("The scenario dataset is empty.")

    ids = [s["scenario_id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate scenario IDs detected.")

    for scenario in scenarios:
        if scenario["expected_tool"] not in TOOLS:
            raise ValueError(
                f"Unknown expected tool in {scenario['scenario_id']}"
            )

    print(f"Loading checkpoint: {CHECKPOINT}", flush=True)

    load_start = time.perf_counter()
    engine = load_engine(CHECKPOINT, device="cuda")
    torch.cuda.synchronize()
    loading_seconds = time.perf_counter() - load_start

    print(f"Model loaded in {loading_seconds:.2f} seconds", flush=True)

    torch.cuda.reset_peak_memory_stats()

    results = []

    for scenario in scenarios:
        question = ChoiceQuestion(
            instructions=scenario["question"],
            criteria=TOOLS,
        )

        torch.cuda.synchronize()
        start = time.perf_counter()

        response = engine.ask(
            scenario["state"],
            {QUESTION_ID: question},
        )

        torch.cuda.synchronize()
        latency_ms = (time.perf_counter() - start) * 1000

        answer = response.answers[QUESTION_ID]
        selected = answer.choice
        expected = scenario["expected_tool"]
        correct = selected == expected

        result = {
            "scenario_id": scenario["scenario_id"],
            "difficulty": scenario["difficulty"],
            "expected_tool": expected,
            "selected_tool": selected,
            "correct": correct,
            "latency_ms": round(latency_ms, 3),
            "probabilities": answer.probabilities,
            "confidence": answer.confidence,
            "usage": response.usage.model_dump(),
        }

        results.append(result)

        status = "PASS" if correct else "FAIL"
        print(
            f"{scenario['scenario_id']} | {status} | "
            f"expected={expected} | selected={selected} | "
            f"{latency_ms:.2f} ms",
            flush=True,
        )

    correct_count = sum(r["correct"] for r in results)
    accuracy = correct_count / len(results)

    report = {
        "benchmark": "benchmark_v01",
        "evaluation_level": "intent_guided",
        "dataset_role": "development",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": CHECKPOINT,
        "model_loading_seconds": round(loading_seconds, 3),
        "gpu_peak_memory_gib": round(
            torch.cuda.max_memory_allocated() / (1024 ** 3), 3
        ),
        "summary": {
            "total": len(results),
            "correct": correct_count,
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1(results), 4),
            "average_latency_ms": round(
                sum(r["latency_ms"] for r in results) / len(results), 3
            ),
            "predictions_by_tool": dict(
                Counter(r["selected_tool"] for r in results)
            ),
        },
        "results": results,
    }

    filename = (
        "benchmark_run_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        + ".json"
    )

    output = RESULTS_DIR / filename
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n========== BENCHMARK SUMMARY ==========")
    print(json.dumps(report["summary"], indent=2))
    print(f"Model loading: {loading_seconds:.2f} seconds")
    print(f"Peak GPU allocated memory: {report['gpu_peak_memory_gib']} GiB")
    print(f"Results saved: {output}")


if __name__ == "__main__":
    main()
