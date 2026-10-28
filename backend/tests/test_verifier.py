"""LLM verifier pass tests (stubbed Muse Spark endpoint, no credentials)."""
from __future__ import annotations

import json

import httpx
import pytest

from backend.agent.llm import MuseSparkClient
from backend.agent.runner import InvestigationRunner
from backend.agent.verifier import verify_with_llm
from backend.config import Settings
from backend.tools import ToolRegistry
from backend.tools.loader import DatasetRepository

CID = "camp_001_bid_low"
REAL_REF = f"query_bid_samples:{CID}:outcome"


def _settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "no-data", state_dir=tmp_path / "state",
                    muse_api_key="k", muse_base_url="http://stub", muse_model="m")


def _client(handler) -> MuseSparkClient:
    return MuseSparkClient("http://stub", "k", "m", transport=httpx.MockTransport(handler))


def _runner(tmp_path):
    settings = _settings(tmp_path)
    registry = ToolRegistry(DatasetRepository(settings.data_dir), settings)
    return InvestigationRunner(settings, registry, lambda *a: None), registry


def _grounded_findings(registry):
    registry.call("query_bid_samples", {"campaign_id": CID, "group_by": "outcome"})
    from backend.agent.findings import Evidence, Finding
    return [Finding(cause="Bid below market", confidence=0.9,
                    evidence=[Evidence(tool="query_bid_samples", ref=REAL_REF,
                                       summary="outbids dominate")])]


def test_verifier_supports_grounded_claim(tmp_path):
    replies = [json.dumps({"supported": True, "reason": "numbers line up"})]
    client = _client(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": replies.pop(0)}}]}))
    runner, registry = _runner(tmp_path)
    findings = _grounded_findings(registry)
    kept, report = verify_with_llm(findings, registry.executed, client)
    assert len(kept) == 1
    assert report.claims_grounded == 1
    assert report.removed == []


def test_verifier_removes_refuted_claim_with_reason(tmp_path):
    replies = [json.dumps({"supported": False, "reason": "win share contradicts claim"})]
    client = _client(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": replies.pop(0)}}]}))
    runner, registry = _runner(tmp_path)
    findings = _grounded_findings(registry)
    kept, report = verify_with_llm(findings, registry.executed, client)
    assert kept == []
    assert "win share contradicts claim" in report.removed[0]


def test_verifier_error_keeps_claim(tmp_path):
    def handler(r):
        return httpx.Response(500, text="boom")
    client = _client(handler)
    runner, registry = _runner(tmp_path)
    findings = _grounded_findings(registry)
    kept, report = verify_with_llm(findings, registry.executed, client)
    assert len(kept) == 1, "verifier outage must not delete grounded work"
    assert report.claims_grounded == 1


def test_runner_combines_rule_based_and_llm_pass(tmp_path):
    # scripted LLM agent: one tool call, then final findings; then verifier refutes
    final_payload = {"findings": [{
        "cause": "stub ok claim", "confidence": 0.9,
        "evidence": [{"tool": "query_bid_samples", "ref": REAL_REF, "summary": "s"}],
        "proposed_changes": []}]}
    agent_replies = [
        {"choices": [{"message": {"tool_calls": [{
            "id": "1", "function": {"name": "query_bid_samples",
                                    "arguments": json.dumps({"campaign_id": CID, "group_by": "outcome"})}}]}}]},
        {"choices": [{"message": {"content": json.dumps(final_payload)}}]},
    ]
    verifier_reply = {"choices": [{"message": {"content": json.dumps(
        {"supported": False, "reason": "stub refutation"})}}]}
    queue = agent_replies + [verifier_reply]

    client = _client(lambda r: httpx.Response(200, json=queue.pop(0)))
    runner, registry = _runner(tmp_path)
    findings, extra = runner.run(CID, "why?", client=client)
    assert findings == []
    v = extra["verifier"]
    assert v.claims_total == 1 and v.claims_grounded == 0
    assert any("stub refutation" in r for r in v.removed)
    assert extra["meta"]["agent_mode"] == "tool-calling"
