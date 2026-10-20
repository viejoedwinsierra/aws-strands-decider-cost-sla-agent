#!/usr/bin/env python3
"""Extracted from EXP-001 infrastructure/create_bucket.sh."""
import os
import tempfile
from pathlib import Path

path = Path(os.environ["CONFIG_FILE"])
bucket = os.environ["BUCKET"]

lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
lines = [line for line in lines if not line.startswith("EVIDENCE_BUCKET=")]
lines.append(f"EVIDENCE_BUCKET={bucket}")

path.parent.mkdir(parents=True, exist_ok=True)

temporary_path = None

try:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write("\n".join(lines) + "\n")
        temporary.flush()
        os.fsync(temporary.fileno())

    if path.exists():
        os.chmod(temporary_path, path.stat().st_mode & 0o777)

    os.replace(temporary_path, path)
finally:
    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)
