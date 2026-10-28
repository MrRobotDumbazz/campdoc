"""LLM agent-mode tests against a stubbed OpenAI-compatible endpoint.

No real credentials needed: httpx.MockTransport scripts the model replies.
Covers: native tool-calling loop, structured-JSON fallback, evidence
enforcement on fabricated refs, and fallback to heuristics on API failure.
"""
from __future__ import annotations

import json

import httpx
import pytest

from backend.agent.llm import MuseSparkClient
from backend.agent.runner import InvestigationRunner
from backend.config import Settings
from backend.tools import ToolRegistry
from backend.tools.loader import DatasetRepository

CID = "camp_001_bid_low"
REAL_REF = f"query_bid_samples:{CID}:outcome"
SETTINGS_REF = f"get_campaign_settings:{CID}"


def _settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "no-data", state_dir=tmp_path / "state",
                    muse_api_key="test-key", muse_base_url="http://stub.local",
                    muse_model="muse-spark-test")


def _client(handler) -> MuseSparkClient:
    return MuseSparkClient("http://stub.local", "test-key", "muse-spark-test",
                           transport=httpx.MockTransport(handler))


def _msg(content=None, tool_calls=None):
    message: dict = {}
    if content is not None:
        message["content"] = content
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}]}


def _tool_call(call_id: str, name: str, arguments: dict):
    return {"id": call_id, "function": {"name": name, "arguments": json.dumps(arguments)}}


def _runner(tmp_path, client=None):
    settings = _settings(tmp_path)
    repo = DatasetRepository(settings.data_dir)
    registry = ToolRegistry(repo, settings)
    traces: list[tuple] = []
    runner = InvestigationRunner(settings, registry, lambda *a: traces.append(a))
    return runner, registry, traces


def _ok_verifier_reply():
    return {"choices": [{"message": {"content": json.dumps(
        {"supported": True, "reason": "numbers line up"})}}]}


def test_tool_calling_loop_produces_grounded_findings(tmp_path):
    replies = [
        _msg(tool_calls=[_tool_call("1", "query_bid_samples",
                                    {"campaign_id": CID, "group_by": "outcome"}),
                         _tool_call("2", "get_campaign_settings", {"campaign_id": CID})]),
        _msg(content=json.dumps({"findings": [{
            "cause": "Bid below market (stub)",
            "evidence": [{"tool": "query_bid_samples", "ref": REAL_REF, "summary": "outbids 70%"},
                         {"tool": "get_campaign_settings", "ref": SETTINGS_REF, "summary": "bid 1.85"}],
            "confidence": 0.9, "proposed_changes": ["Raise bid by 20%"]}]})),
        _ok_verifier_reply(),  # verifier pass supports the claim
    ]
    client = _client(lambda req: httpx.Response(200, json=replies.pop(0)))
    runner, registry, traces = _runner(tmp_path)
    findings, extra = runner.run(CID, "why?", client=client)

    assert extra["meta"]["agent_mode"] == "tool-calling"
    assert len(findings) == 1
    assert findings[0].cause == "Bid below market (stub)"
    assert {e.ref for e in findings[0].evidence} == {REAL_REF, SETTINGS_REF}
    assert extra["verifier"].claims_grounded == 1
    # both tool executions went through the registry (evidence ledger)
    assert REAL_REF in registry.executed and SETTINGS_REF in registry.executed
    assert any(t[0] == "tool" and t[1] == "query_bid_samples" for t in traces)


def test_fabricated_evidence_ref_is_removed(tmp_path):
    replies = [
        _msg(content=json.dumps({"findings": [{
            "cause": "gremlins in the DSP",
            "evidence": [{"tool": "query_bid_samples", "ref": "totally:made:up", "summary": "trust me"}],
            "confidence": 0.99, "proposed_changes": []}]})),
    ]
    client = _client(lambda req: httpx.Response(200, json=replies.pop(0)))
    runner, registry, _ = _runner(tmp_path)
    findings, extra = runner.run(CID, "why?", client=client)
    assert findings == []
    assert extra["verifier"].claims_total == 1
    assert extra["verifier"].claims_grounded == 0
    assert "totally:made:up" in extra["verifier"].removed[0]


def test_json_prompting_fallback_when_no_tool_calls(tmp_path):
    replies = [
        _msg(content='Sure! {"tool": "get_campaign_settings", "arguments": {"campaign_id": "%s"}}' % CID),
        _msg(content=json.dumps({"findings": [{
            "cause": "stub cause via json mode",
            "evidence": [{"tool": "get_campaign_settings", "ref": SETTINGS_REF, "summary": "s"}],
            "confidence": 0.8, "proposed_changes": []}]})),
        _ok_verifier_reply(),
    ]
    client = _client(lambda req: httpx.Response(200, json=replies.pop(0)))
    runner, registry, _ = _runner(tmp_path)
    findings, extra = runner.run(CID, "why?", client=client)
    assert extra["meta"]["agent_mode"] == "json-prompting"
    assert [f.cause for f in findings] == ["stub cause via json mode"]
    assert SETTINGS_REF in registry.executed


def test_api_failure_falls_back_to_heuristics(tmp_path):
    def handler(req):
        return httpx.Response(401, json={"error": "bad key"})
    client = _client(handler)
    runner, registry, _ = _runner(tmp_path)
    findings, extra = runner.run(CID, "why?", client=client)
    assert extra["meta"]["agent_mode"] == "heuristic"
    assert "LLMUnavailableError" in extra["meta"]["llm_note"]
    assert findings, "heuristic engine must still diagnose offline"
    assert all(f.evidence for f in findings)


def test_max_steps_guard_raises_and_falls_back(tmp_path):
    infinite_tools = lambda req: httpx.Response(200, json=_msg(  # noqa: E731
        tool_calls=[_tool_call("x", "query_bid_samples", {"campaign_id": CID, "group_by": "outcome"})]))
    client = _client(infinite_tools)
    runner, registry, _ = _runner(tmp_path)
    settings = runner.settings
    object.__setattr__(settings, "agent_max_steps", 3)
    findings, extra = runner.run(CID, "why?", client=client)
    assert extra["meta"]["agent_mode"] == "heuristic"
    assert "RuntimeError" in extra["meta"]["llm_note"]
