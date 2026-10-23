"""S3 -> local evidence replication, separate from experiment runners."""
import subprocess
from pathlib import Path


def sync_sources(sources: list[dict], root: Path, profile: str, region: str) -> list[Path]:
    roots = []
    for source in sources:
        target = root / source["id"]
        target.mkdir(parents=True, exist_ok=True)
        cmd = ["aws", "--profile", profile, "--region", region, "s3", "sync", source["uri"], str(target), "--only-show-errors"]
        subprocess.run(cmd, check=True)
        roots.append(target)
    return roots
