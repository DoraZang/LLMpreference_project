"""
Call the model and record everything needed to reproduce each call.

Uses the OpenAI Responses API: the system message is passed as `instructions`
and the item as `input`. Temperature is set to 1 only when reasoning effort is
"none"; the API does not accept temperature when reasoning is on.
See notes/lab_log.md (2026-10-25, Model choice).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

MODEL = "gpt-6-luna"
PRICE_PER_M = {"input": 0.10, "output": 0.50}   # USD per 1M tokens, standard (non-batch) rate

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def request_params(system, user, reasoning_effort="none", max_output_tokens=None, long_output=False):
    """Request body for one call. Shared by direct calls and the Batch API, so both send identical requests.

    long_output: the answer format asks for written reasoning (e.g. CoT), so the
    non-reasoning cap is raised from 500 to 2000 tokens.
    """
    if max_output_tokens is None:
        # Reasoning tokens count toward the cap, so reasoning mode needs a much higher limit
        if reasoning_effort != "none":
            max_output_tokens = 16000
        else:
            max_output_tokens = 2000 if long_output else 500
    params = {
        "model": MODEL,
        "instructions": system,
        "input": user,
        "reasoning": {"effort": reasoning_effort},
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    if reasoning_effort == "none":
        params["temperature"] = 1
    return params


def summarize_response(response, params):
    """Call metadata and output from a Response object (direct call or Batch API result)."""
    usage = response.usage
    details = usage.output_tokens_details
    return {
        "timestamp": datetime.fromtimestamp(response.created_at, timezone.utc).isoformat(),
        "model_requested": params["model"],
        "reasoning_effort": params["reasoning"]["effort"],
        "temperature": params.get("temperature"),
        "max_output_tokens": params["max_output_tokens"],
        "model_returned": response.model,
        "response_id": response.id,
        "status": response.status,
        "incomplete_reason": response.incomplete_details.reason if response.incomplete_details else None,
        "output_text": response.output_text,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": details.reasoning_tokens if details else None,
    }


def call_model(system, user, reasoning_effort="none", max_output_tokens=None, long_output=False):
    """Send one request directly (not through the Batch API)."""
    params = request_params(system, user, reasoning_effort, max_output_tokens, long_output)
    response = get_client().responses.create(**params)
    return summarize_response(response, params)


def cost_usd(call):
    """Approximate cost of one call at the standard rate."""
    return (call["input_tokens"] * PRICE_PER_M["input"]
            + call["output_tokens"] * PRICE_PER_M["output"]) / 1e6


def append_jsonl(path, record):
    """Append one record to a JSONL file. Raw data is append-only: never edit existing lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    # Connection test: exactly ONE non-reasoning call on one item (cost far below one cent).
    import random
    from prompts import build_prompt, load_items
    from parse import analyze

    items = {it["item_id"]: it for it in load_items()}
    item = items["gain_03"]
    prompt = build_prompt(item, version=1, rng=random.Random())

    call = call_model(prompt["system"], prompt["user"], reasoning_effort="none")
    record = {"run": "connection_test", "condition": "baseline", **prompt, **call}
    append_jsonl(ROOT / "data" / "raw" / "connection_test.jsonl", record)

    print(f"Model returned: {call['model_returned']} | status: {call['status']}")
    print(f"Tokens: input {call['input_tokens']}, output {call['output_tokens']}, "
          f"reasoning {call['reasoning_tokens']} | cost ~ ${cost_usd(call):.6f}")
    print("-" * 70)
    print(call["output_text"])
    print("-" * 70)
    result = analyze(item, prompt, call["output_text"])
    print({k: result[k] for k in ("status", "pattern", "ce", "risk_premium")})