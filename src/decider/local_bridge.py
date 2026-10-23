"""Offline Strands Decider CLI bridge. JSON stdin -> JSON stdout."""
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_CHECKPOINT = (
    "/home/edwin/.cache/huggingface/hub/"
    "models--StrandsAgents--strands-decider-2B-hobson-v21/"
    "snapshots/2b52a6235c1b8306bbfa30b00b9d4b74b63a39f5"
)

def main():
    payload = json.load(sys.stdin)
    checkpoint = os.environ.get("INFRAVITA_DECIDER_CHECKPOINT", DEFAULT_CHECKPOINT)
    device = os.environ.get("INFRAVITA_DECIDER_DEVICE", "cuda")
    executable = Path(sys.executable).with_name("strands-decider")

    if not Path(checkpoint).is_dir():
        raise SystemExit("Checkpoint local no encontrado")

    options = payload["options"]
    question = payload["question"]
    state = payload["state"]

    command = [
        str(executable), "ask", checkpoint,
        "--state", state,
        "--choice", question + "=" + ",".join(options),
        "--device", device,
        "--json",
    ]

    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"

    result = subprocess.run(
        command, capture_output=True, text=True,
        env=env, timeout=240, check=True
    )

    response = json.loads(result.stdout)
    if "answers" not in response:
        raise ValueError("Respuesta sin answers")

    print(json.dumps(response))

if __name__ == "__main__":
    main()
