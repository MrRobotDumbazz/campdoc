#!/usr/bin/env python3
"""Day-1 check: does Muse Spark (Meta Model API) support native tool calling?

Usage:
  python backend/scripts/check_tool_calling.py

Env required: MUSE_SPARK_BASE_URL, MUSE_SPARK_API_KEY (MUSESPARK_API_KEY),
optional MUSE_SPARK_MODEL (default: muse-spark).

Outcome:
  - TOOL_CALLING_OK   -> native tool_calls present, agent uses them;
  - JSON_FALLBACK_OK  -> model replies with parseable JSON action (structured
                         JSON prompting fallback, PRD risk table);
  - SKIP              -> no credentials in env (heuristic offline mode);
  - FAIL              -> transport/protocol error (message printed).
Exit codes: 0 on OK/FALLBACK/SKIP, 1 on FAIL.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.agent.llm import (LLMParseError, LLMUnavailableError,  # noqa: E402
                               MuseSparkClient, extract_json)

TOOL = [{
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Reply with pong.",
        "parameters": {"type": "object", "properties": {}},
    },
}]


def main() -> int:
    base = os.environ.get("MUSE_SPARK_BASE_URL")
    key = os.environ.get("MUSE_SPARK_API_KEY") or os.environ.get("MUSESPARK_API_KEY")
    model = os.environ.get("MUSE_SPARK_MODEL", "muse-spark")
    if not base or not key:
        print("SKIP: set MUSE_SPARK_BASE_URL and MUSE_SPARK_API_KEY to run this check "
              "(until then the backend runs in deterministic heuristic mode).")
        return 0
    try:
        client = MuseSparkClient(base, key, model)
        resp = client.chat(
            [{"role": "user",
              "content": "Call the tool named ping. If you cannot call tools, reply with "
                         'JSON {"tool": "ping", "arguments": {}}.'}],
            tools=TOOL)
    except (LLMUnavailableError, OSError) as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1
    if resp.wants_tool:
        print(f"TOOL_CALLING_OK: model={model} returned tool_calls -> native tool calling enabled")
        return 0
    try:
        payload = extract_json(resp.content or "")
        if isinstance(payload, dict) and payload.get("tool") == "ping":
            print(f"JSON_FALLBACK_OK: model={model} replied with a parseable JSON action "
                  "-> use structured-JSON prompting mode")
            return 0
        print(f"FAIL: unexpected reply payload: {str(payload)[:200]}")
        return 1
    except LLMParseError as e:
        print(f"FAIL: no tool_calls and no parseable JSON ({e}); raw head: {(resp.content or '')[:200]}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
