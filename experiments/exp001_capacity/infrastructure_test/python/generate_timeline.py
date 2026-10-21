#!/usr/bin/env python3
import json
import sys
from datetime import datetime
from pathlib import Path

(
    output, experiment, run_id, load_status,
    pre_start, pre_end, run_start, run_end,
    post_start, post_end,
) = sys.argv[1:]

def duration(start, end):
    return (
        datetime.fromisoformat(end.replace("Z", "+00:00"))
        - datetime.fromisoformat(start.replace("Z", "+00:00"))
    ).total_seconds()

timeline = {
    "schema_version": "1.0",
    "experiment_id": experiment,
    "run_id": run_id,
    "load_exit_code": int(load_status),
    "phases": {
        "PRE": {
            "start_utc": pre_start,
            "end_utc": pre_end,
            "duration_seconds": duration(pre_start, pre_end),
        },
        "RUN": {
            "start_utc": run_start,
            "end_utc": run_end,
            "duration_seconds": duration(run_start, run_end),
            "window_type": "operational",
        },
        "POST": {
            "start_utc": post_start,
            "end_utc": post_end,
            "duration_seconds": duration(post_start, post_end),
        },
    },
    "cloudwatch_window": {
        "start_utc": pre_start,
        "end_utc": post_end,
        "duration_seconds": duration(pre_start, post_end),
    },
}

Path(output).write_text(
    json.dumps(timeline, indent=2) + "\n",
    encoding="utf-8",
)
print(f"EXP-001 | Timeline saved: {output}")
