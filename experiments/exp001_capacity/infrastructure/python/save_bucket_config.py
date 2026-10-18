#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/create_bucket.sh."""
import os
from pathlib import Path

path = Path(os.environ["CONFIG_FILE"])
bucket = os.environ["BUCKET"]

lines = path.read_text().splitlines() if path.exists() else []
lines = [line for line in lines if not line.startswith("EVIDENCE_BUCKET=")]
lines.append(f"EVIDENCE_BUCKET={bucket}")

path.write_text("\n".join(lines) + "\n")
