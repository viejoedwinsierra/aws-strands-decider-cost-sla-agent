#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/create_bucket.sh."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

p = Path(os.environ["HISTORY_FILE"])
history = json.loads(p.read_text()) if p.exists() else []
history.append({
    "bucket": os.environ["OLD_BUCKET"],
    "replaced_at_utc": datetime.now(timezone.utc).isoformat(),
    "reason": "Bucket inaccessible during AWS Academy recovery"
})
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(history, indent=2) + "\n")
