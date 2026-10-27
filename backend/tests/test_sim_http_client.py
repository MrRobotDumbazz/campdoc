"""Contract tests for HttpSimulationClient (seam to zone B, /contracts/simulation.api.yaml).

The stub server stands in for the real simulator (B2): we verify the request
shape we send and enforce the response fields the contract promises, so the
real simulator can be wired in Day 4-5 by setting SIMULATOR_BASE_URL only.
"""
from __future__ import annotations

import httpx
import pytest

from backend.config import Settings
from backend.tools import make_simulation_client
from backend.tools.base import ToolError
from backend.tools.loader import DatasetRepository
from backend.tools.sim_client import HttpSimulationClient

CONTRACT_OUTPUT = {
    "before": {"impressions": 18000, "spend": 41.4, "win_rate": 0.30, "ecpm": 2.30},
    "after": {"impressions": 27000, "spend": 62.1, "win_rate": 0.45, "ecpm": 2.30},
    "delta": {"impressions": 9000, "spend": 20.7, "win_rate": 0.15, "ecpm": 0.0},
    "verified": True,
    "threshold_pct": 5.0,
    "violated_constraints": [],
    "notes": ["Симуляция на выборке bid-запросов; прогноз, не гарантия"],
}


def make_client(handler) -> HttpSimulationClient:
    return HttpSimulationClient("http://sim.stub", transport=httpx.MockTransport(handler))


def test_request_shape_matches_contract():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("authorization")
        import json as _json
        captured["json"] = _json.loads(request.content)
        return httpx.Response(200, json=CONTRACT_OUTPUT)

    client = make_client(handler)
    out = client.run_simulation("camp_001_bid_low", 42, {"bid_delta_pct": 20},
                                {"max_ecpm": 3.0}, "impressions")
    assert captured["path"] == "/simulate"
    body = captured["json"]
    assert body["campaign_id"] == "camp_001_bid_low"
    assert body["seed"] == 42
    assert body["changes"] == {"bid_delta_pct": 20}
    assert body["constraints"] == {"max_ecpm": 3.0}
    assert body["target_metric"] == "impressions"
    assert out == CONTRACT_OUTPUT


def test_response_missing_contract_field_rejected():
    bad = {k: v for k, v in CONTRACT_OUTPUT.items() if k != "violated_constraints"}
    client = make_client(lambda r: httpx.Response(200, json=bad))
    with pytest.raises(ToolError) as e:
        client.run_simulation("c", 1, {}, None)
    assert "violates contract" in str(e.value) and "violated_constraints" in str(e.value)


def test_http_error_surfaces_as_tool_error():
    client = make_client(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(ToolError) as e:
        client.run_simulation("c", 1, {}, None)
    assert "HTTP 500" in str(e.value)


def test_factory_selects_http_client_when_configured(tmp_path):
    settings = Settings(data_dir=tmp_path / "no", state_dir=tmp_path,
                        simulator_base_url="http://sim.stub")
    repo = DatasetRepository(settings.data_dir)
    client = make_simulation_client(repo, settings)
    assert isinstance(client, HttpSimulationClient)
    assert client.name == "http"
    client._client.close()
