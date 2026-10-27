"""Muse Spark client (Meta Model API, chat-completions style).

Endpoints/URLs and credentials come exclusively from env (I52):
  MUSE_SPARK_BASE_URL, MUSE_SPARK_API_KEY (or MUSESPARK_API_KEY), MUSE_SPARK_MODEL.

Two interaction modes (PRD 6.2 / risk table):
- native tool calling (tools=... -> tool_calls in response);
- structured-JSON fallback: the model answers with a JSON object
  {"tool": name, "arguments": {...}} or {"findings": [...]}, which we parse.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx


class LLMUnavailableError(Exception):
    """No credentials/base URL configured -> caller falls back to heuristic mode."""


class LLMParseError(Exception):
    pass


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)  # [{name, arguments(dict)}]
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def wants_tool(self) -> bool:
        return bool(self.tool_calls)


class MuseSparkClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 60.0):
        if not base_url or not api_key:
            raise LLMUnavailableError("Muse Spark credentials are not configured (env MUSE_SPARK_BASE_URL / MUSE_SPARK_API_KEY).")
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s,
                                  headers={"Authorization": f"Bearer {api_key}"})
        self.model = model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
             temperature: float = 0.2) -> LLMResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            payload["tools"] = tools
        resp = self._http.post("/chat/completions", json=payload)
        if resp.status_code >= 400:
            raise LLMUnavailableError(f"Muse Spark HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function", {})
            args = fn.get("arguments")
            if isinstance(args, str):
                args = _loads_lenient(args)
            calls.append({"name": fn.get("name"), "arguments": args or {}, "id": c.get("id")})
        return LLMResponse(content=msg.get("content"), tool_calls=calls, raw=data)


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.S)


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array from a model reply (fenced or bare)."""
    if not text:
        raise LLMParseError("empty model reply")
    m = _JSON_BLOCK.search(text)
    if m:
        return _loads_lenient(m.group(1))
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise LLMParseError("no JSON found in model reply")
    depth = 0
    open_ch, close_ch = text[start], "}" if text[start] == "{" else "]"
    for i in range(start, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return _loads_lenient(text[start:i + 1])
    raise LLMParseError("unbalanced JSON in model reply")


def _loads_lenient(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise LLMParseError(f"invalid JSON from model: {e}") from e
