"""Validate and load configured S3 evidence sources."""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


def load_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML missing: run scripts/setup_agent.sh once") from exc
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("sources"), list):
        raise ValueError("Configuration requires a sources list")
    sources = []
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        source_id = source.get("id", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", source_id):
            raise ValueError(f"Invalid source id: {source_id}")
        uri = source.get("uri", "")
        for variable in re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\}", uri):
            if variable != "EVIDENCE_BUCKET" or not os.environ.get(variable):
                raise ValueError(f"Missing or disallowed variable: {variable}")
            uri = uri.replace("${" + variable + "}", os.environ[variable])
        parsed = urlsplit(uri)
        if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/") or parsed.query or parsed.fragment:
            raise ValueError(f"Invalid S3 prefix: {uri}")
        if ".." in parsed.path.split("/"):
            raise ValueError("Invalid S3 prefix traversal")
        sources.append({"id": source_id, "uri": uri.rstrip("/") + "/"})
    if len({s["id"] for s in sources}) != len(sources):
        raise ValueError("Duplicate source IDs")
    return {"sources": sources, "interval_seconds": max(10, int(config.get("discovery", {}).get("interval_seconds", 60)))}
