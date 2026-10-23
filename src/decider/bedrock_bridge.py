"""Amazon Bedrock inference bridge. JSON stdin -> JSON stdout."""

import json
import os
import sys


OPTIONS = (
    "Maintain",
    "Optimize",
    "Scale Up",
    "Insufficient Evidence",
)


def main():
    import boto3

    payload = json.load(sys.stdin)

    for field in ("experiment_id", "run_id", "state", "question", "options"):
        if field not in payload:
            raise ValueError(f"Missing input field: {field}")

    if set(payload["options"]) != set(OPTIONS):
        raise ValueError("Unsupported decision options")

    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required")

    region = os.environ.get("INFRAVITA_BEDROCK_REGION", "us-east-2")
    model_id = os.environ.get(
        "INFRAVITA_BEDROCK_MODEL_ID",
        "us.amazon.nova-micro-v1:0",
    )

    client = boto3.client("bedrock-runtime", region_name=region)

    instructions = (
        "You are an infrastructure decision analyst. "
        "Use only the provided evidence. "
        "Return exactly one JSON object with fields "
        "'choice' and 'reason'. "
        "The choice must be one of: "
        + ", ".join(OPTIONS)
        + ". Do not invent measurements. "
        "When evidence is insufficient, choose Insufficient Evidence. "
        "A recommendation is provisional and subject to deterministic guardrails."
    )

    request = {
        "experiment_id": payload["experiment_id"],
        "run_id": payload["run_id"],
        "question": payload["question"],
        "state": payload["state"],
        "options": payload["options"],
    }

    response = client.converse(
        modelId=model_id,
        system=[{"text": instructions}],
        messages=[
            {
                "role": "user",
                "content": [{"text": json.dumps(request)}],
            }
        ],
        inferenceConfig={"maxTokens": 300, "temperature": 0},
    )

    content = response["output"]["message"]["content"]
    text = "\n".join(item["text"] for item in content if "text" in item)
    text = text.strip()

    # Accept a plain JSON object or a JSON object in a markdown code fence.
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or not lines[-1].strip() == "```":
            raise ValueError("Invalid Bedrock JSON code fence")
        text = "\n".join(lines[1:-1]).strip()

    result = json.loads(text)

    if not isinstance(result, dict):
        raise ValueError("Bedrock response must be a JSON object")

    choice = result.get("choice")
    reason = result.get("reason")

    if choice not in OPTIONS:
        raise ValueError(f"Unsupported Bedrock decision: {choice}")

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Bedrock response missing reason")

    output = {
        "answers": {
            "choice_0": {
                "choice": choice,
                "probabilities": {choice: None},
                "confidence": None,
            }
        },
        "provider": "amazon-bedrock",
        "model_id": model_id,
        "region": region,
        "reason": reason,
        "confidence_calibrated": False,
        "usage": response.get("usage", {}),
        "request_id": response.get("ResponseMetadata", {}).get(
            "RequestId"
        ),
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
