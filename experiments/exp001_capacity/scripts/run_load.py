#!/usr/bin/env python3
"""EXP-001: bounded, reproducible HTTP load test."""

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def percentile(values, p):
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def request(url, timeout):
    start = time.perf_counter()
    try:
        with urlopen(url, timeout=timeout) as response:
            response.read()
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, TimeoutError, OSError):
        status = 0

    return {
        "status": status,
        "latency_ms": (time.perf_counter() - start) * 1000,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080/work?iterations=1000")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    if not 1 <= args.requests <= 1000:
        parser.error("requests must be between 1 and 1000")
    if not 1 <= args.concurrency <= 10:
        parser.error("concurrency must be between 1 and 10")
    if not 0 < args.timeout <= 10:
        parser.error("timeout must be between 0 and 10 seconds")
    if not args.url.startswith("http://127.0.0.1:8080/"):
        parser.error("Only the local EXP-001 server is allowed")

    started_at = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(request, args.url, args.timeout)
            for _ in range(args.requests)
        ]
        results = [future.result() for future in as_completed(futures)]

    duration = time.perf_counter() - start
    latencies = [item["latency_ms"] for item in results]
    errors = sum(not 200 <= item["status"] < 400 for item in results)

    summary = {
        "experiment": "EXP-001",
        "started_at_utc": started_at,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "duration_sec": round(duration, 4),
        "throughput_rps": round(args.requests / duration, 2),
        "errors": errors,
        "error_rate": round(errors / args.requests, 4),
        "latency_p50_ms": round(percentile(latencies, 50), 3),
        "latency_p95_ms": round(percentile(latencies, 95), 3),
        "latency_p99_ms": round(percentile(latencies, 99), 3),
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
