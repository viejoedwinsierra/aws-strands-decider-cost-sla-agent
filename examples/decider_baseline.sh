#!/usr/bin/env bash
set -euo pipefail

MODEL="${DECIDER_MODEL:-StrandsAgents/strands-decider-2B-hobson-v19}"
DEVICE="${DECIDER_DEVICE:-cuda}"
OUTPUT="${1:-/tmp/decider_baseline.json}"

mkdir -p "$(dirname "$OUTPUT")"

strands-decider ask "$MODEL" \
  --device "$DEVICE" \
  --state "An AWS HTTP service has p95 latency of 5 ms against a 100 ms SLA threshold, an error rate of 0% against a 1% limit, and throughput of 4.99 requests per second against a minimum of 4. No CPU utilization, capacity headroom, or infrastructure cost measurements are available." \
  --choice "What is the most justified operational recommendation?=Maintain,Optimize,Scale Up,Insufficient Evidence" \
  --json > "$OUTPUT"

python -m json.tool "$OUTPUT" > /dev/null

echo "Decider baseline completed: $OUTPUT"
