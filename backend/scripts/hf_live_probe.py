#!/usr/bin/env python3
"""Live probe: Muse Spark Open via Hugging Face router through OUR stack.

Token source (never in chat/logs, I52): env HF_TOKEN or ~/.hf_token file.
Usage:
  HF_TOKEN=$(cat ~/.hf_token) backend/.venv/bin/python backend/scripts/hf_live_probe.py
Optional: MUSE_SPARK_MODEL=meta-models/Muse-Spark-Open-816B-A42B-NVFP4:together
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.agent.llm import MuseSparkClient  # noqa: E402
from backend.config import (HF_DEFAULT_BASE_URL, HF_DEFAULT_MODEL,  # noqa: E402
                            Settings)

TOKEN_FILE = Path.home() / ".hf_token"


def get_token() -> str | None:
    tok = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
    if tok:
        return tok
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text().strip()
    return None


def main() -> int:
    token = get_token()
    if not token:
        print("NO TOKEN: env HF_TOKEN or ~/.hf_token is missing")
        return 2
    model = os.environ.get("MUSE_SPARK_MODEL", HF_DEFAULT_MODEL)
    settings = Settings(muse_api_key=token, muse_key_source="hf",
                        muse_base_url=os.environ.get("MUSE_SPARK_BASE_URL",
                                                     HF_DEFAULT_BASE_URL),
                        muse_model=model)
    print(f"probe: base_url={settings.muse_base_url} model={settings.muse_model} "
          f"backend={settings.llm_backend}")
    client = MuseSparkClient(settings.muse_base_url, settings.muse_api_key,
                             settings.muse_model, timeout_s=90)

    # 1) text ping
    resp = client.chat([{"role": "user", "content": "Reply with the single word: pong"}])
    text = (resp.content or "").strip()
    print(f"[1] text ping -> {text!r}")

    # 2) tool-calling probe (agent format, tools/__init__.py)
    tools = [{
        "type": "function",
        "function": {
            "name": "query_delivery",
            "description": "Aggregate delivery metrics for a campaign",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string",
                               "enum": ["impressions", "spend", "bids", "wins"]},
                    "group_by": {"type": "string"},
                },
                "required": ["metric"],
            },
        },
    }]
    resp2 = client.chat(
        [{"role": "user",
          "content": "How many impressions did campaign fm1 deliver? "
                     "Use the query_delivery tool."}],
        tools=tools, temperature=0.0)
    if resp2.wants_tool and resp2.tool_calls:
        call = resp2.tool_calls[0]
        print(f"[2] tool-calling -> OK: {call['name']}({call['arguments']})")
    else:
        print(f"[2] tool-calling -> NO TOOL CALL, content={((resp2.content or '')[:200])!r}")
        print("    (the agent will fall back to structured JSON prompting — the fallback is documented)")
    print("probe done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
