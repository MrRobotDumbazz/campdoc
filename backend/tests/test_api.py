"""Contract tests for the five /contracts/app.api.yaml endpoints (heuristic offline mode)."""
from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.config import Settings


def make_client(tmp_path) -> TestClient:
    settings = Settings(data_dir=tmp_path / "nonexistent-data", state_dir=tmp_path / "state")
    app = create_app(settings)
    return TestClient(app)


def test_health_reports_backend_and_model(tmp_path):
    client = make_client(tmp_path)
    out = client.get("/api/health").json()
    assert out["ok"] is True
    assert out["agent_mode"] == "heuristic"
    assert out["llm_backend"] == "auto"  # no Muse Spark env creds in offline mode
    assert "llm_model" in out
    assert out["data_source"] == "mock"


def test_health_backend_open_weights_prefix(tmp_path):
    settings = Settings(data_dir=tmp_path / "no-data", state_dir=tmp_path / "state",
                        muse_api_key="k", muse_base_url="http://stub",
                        muse_model="meta-models/muse-spark-open-1026")
    out = TestClient(create_app(settings)).get("/api/health").json()
    assert out["agent_mode"] == "llm"
    assert out["llm_backend"] == "open_weights"


def test_health_backend_meta_api(tmp_path):
    settings = Settings(data_dir=tmp_path / "no-data", state_dir=tmp_path / "state",
                        muse_api_key="k", muse_base_url="http://stub",
                        muse_model="muse-spark")
    out = TestClient(create_app(settings)).get("/api/health").json()
    assert out["llm_backend"] == "meta_api"


def test_health_real_datasets_when_present(tmp_path):
    """Default config must pick up the shared data/datasets dir (seam /data)."""
    from backend.config import REPO_ROOT
    datasets = REPO_ROOT / "data" / "datasets"
    if not datasets.is_dir():
        import pytest
        pytest.skip("shared data/datasets not present in this checkout")
    settings = Settings(state_dir=tmp_path / "state")
    assert settings.data_dir == datasets
    out = TestClient(create_app(settings)).get("/api/health").json()
    assert out["data_source"] == "data-dir"
    ids = {d["campaign_id"] for d in TestClient(create_app(settings)).get("/api/datasets").json()["datasets"]}
    assert {"control_healthy", "fm1_bid_low"} <= ids


def wait_done(client: TestClient, inv_id: str, timeout_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        out = client.get(f"/api/investigations/{inv_id}").json()
        if out["status"] in ("done", "error"):
            return out
        time.sleep(0.05)
    raise AssertionError("investigation did not finish in time")


def test_datasets_endpoint(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    ds = resp.json()["datasets"]
    ids = {d["campaign_id"] for d in ds}
    assert len(ds) >= 5
    assert "control_healthy" in ids
    healthy = [d for d in ds if d["campaign_id"] == "control_healthy"]
    assert healthy[0]["healthy"] is True


def test_ask_and_investigation_flow(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/api/ask", json={"campaign_id": "camp_001_bid_low",
                                         "question": "Why is delivery at 55% of budget?"})
    assert resp.status_code == 202
    inv_id = resp.json()["investigation_id"]

    out = wait_done(client, inv_id)
    assert out["status"] == "done", out
    assert out["question"].startswith("Why is delivery")
    assert out["trace"], "trace must not be empty"
    for step in out["trace"]:
        assert {"ts", "step", "tool", "input_summary", "output_summary"} <= set(step)
    assert out["findings"], "findings expected for a broken campaign"
    for f in out["findings"]:
        assert f["evidence"], "no evidence -> no diagnosis (code-level rule)"
        assert 0.0 <= f["confidence"] <= 1.0
    assert out["verifier"]["claims_total"] >= len(out["findings"])
    assert out["verifier"]["claims_grounded"] == len(out["findings"])


def test_healthy_control_no_false_positive(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/api/ask", json={"campaign_id": "control_healthy",
                                         "question": "Anything wrong with this campaign?"})
    inv_id = resp.json()["investigation_id"]
    out = wait_done(client, inv_id)
    assert out["status"] == "done"
    causes = " ".join(f["cause"].lower() for f in out["findings"])
    assert "no major issue" in causes
    assert all(not f["proposed_changes"] for f in out["findings"])


def test_ask_unknown_campaign(tmp_path):
    client = make_client(tmp_path)
    resp = client.post("/api/ask", json={"campaign_id": "nope", "question": "?"})
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "unknown campaign"


def test_simulate_fix_contract_and_determinism(tmp_path):
    client = make_client(tmp_path)
    inv_id = client.post("/api/ask", json={"campaign_id": "camp_001_bid_low",
                                           "question": "Why underdelivering?"}).json()["investigation_id"]
    wait_done(client, inv_id)

    r1 = client.post(f"/api/investigations/{inv_id}/fixes/0/simulate", json={"seed": 42})
    assert r1.status_code == 200
    body = r1.json()
    for k in ("before", "after", "delta"):
        assert {"impressions", "spend", "win_rate", "ecpm"} <= set(body[k])
    assert isinstance(body["verified"], bool)
    assert body["threshold_pct"] == 5.0
    assert isinstance(body["violated_constraints"], list)
    assert any("не гарантия" in n or "прогноз" in n for n in body["notes"])

    r2 = client.post(f"/api/investigations/{inv_id}/fixes/0/simulate", json={"seed": 42})
    assert r2.json() == body, "same input+seed must give identical output"

    r404 = client.post(f"/api/investigations/{inv_id}/fixes/99/simulate", json={"seed": 1})
    assert r404.status_code == 404


def test_report_md(tmp_path):
    client = make_client(tmp_path)
    inv_id = client.post("/api/ask", json={"campaign_id": "camp_003_freq_cap",
                                           "question": "Reach is low, why?"}).json()["investigation_id"]
    wait_done(client, inv_id)
    resp = client.get(f"/api/investigations/{inv_id}/report.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "Campaign Doctor" in resp.text
    assert "Evidence" in resp.text
    assert "Verifier" in resp.text


def test_unknown_investigation(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/investigations/deadbeef").status_code == 404


def test_state_persisted_to_disk(tmp_path):
    client = make_client(tmp_path)
    inv_id = client.post("/api/ask", json={"campaign_id": "camp_005_asap",
                                           "question": "Budget gone too fast?"}).json()["investigation_id"]
    wait_done(client, inv_id)
    inv_dir = tmp_path / "state" / "investigations"
    final = json.loads((inv_dir / f"{inv_id}.json").read_text(encoding="utf-8"))
    assert final["status"] == "done"
    assert final["findings"], "persisted snapshot must include findings"
    assert final["fixes"], "persisted snapshot must include flattened fixes"
    trace_lines = (inv_dir / f"{inv_id}.trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(trace_lines) >= 5, "every tool call must be trace-logged (PRD 6.4)"
    assert all(json.loads(l)["step"] for l in trace_lines)


def test_report_pending_while_running(tmp_path):
    client = make_client(tmp_path)
    inv_id = client.post("/api/ask", json={"campaign_id": "camp_006_floors",
                                           "question": "Why?"}).json()["investigation_id"]
    resp = client.get(f"/api/investigations/{inv_id}/report.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")


def test_report_includes_simulation_results(tmp_path):
    client = make_client(tmp_path)
    inv_id = client.post("/api/ask", json={"campaign_id": "camp_001_bid_low",
                                           "question": "Why underdelivering?"}).json()["investigation_id"]
    wait_done(client, inv_id)
    sim = client.post(f"/api/investigations/{inv_id}/fixes/0/simulate", json={"seed": 7})
    assert sim.status_code == 200
    report = client.get(f"/api/investigations/{inv_id}/report.md").text
    assert "verified" in report
    assert "| metric | before | after | delta |" in report
    assert "Plain English" in report
    # snapshot on disk contains the recorded simulation too
    snap = json.loads((tmp_path / "state" / "investigations" / f"{inv_id}.json").read_text())
    assert "simulations" in snap["meta"] and "0" in snap["meta"]["simulations"]


def test_simulate_uses_fix_target_direction_and_returns_pacing(tmp_path, monkeypatch):
    """v1-draft.1: the fix's own target (fm7 mock: spend+decrease) goes to the
    simulator unless the request overrides it; the pacing block passes through."""
    captured: dict = {}

    class _StubSim:
        name = "stub"

        def run_simulation(self, campaign_id, seed, changes, constraints,
                           target_metric="impressions", target_direction="increase"):
            captured.update(metric=target_metric, direction=target_direction,
                            changes=changes)
            return {
                "before": {"impressions": 12594, "spend": 19588.03, "win_rate": 0.5, "ecpm": 1.55},
                "after": {"impressions": 9115, "spend": 18571.0, "win_rate": 0.45, "ecpm": 2.04},
                "delta": {"impressions": -3479, "spend": -1017.03, "win_rate": -0.05, "ecpm": 0.49},
                "verified": True, "threshold_pct": 5.0, "violated_constraints": [],
                "notes": ["n"],
                "pacing": {"before": {"active_days": 14, "active_hours": 24,
                                      "budget_utilization": 0.98},
                           "after": {"active_days": 14, "active_hours": 24,
                                     "budget_utilization": 0.93}},
            }

    monkeypatch.setattr("backend.api.main.make_simulation_client",
                        lambda repo, settings: _StubSim())
    settings = Settings(data_dir=tmp_path / "no-data", state_dir=tmp_path / "state")
    client = TestClient(create_app(settings))
    inv_id = client.post("/api/ask", json={"campaign_id": "camp_007_sellers",
                                           "question": "Where does the budget go?"}).json()["investigation_id"]
    wait_done(client, inv_id)

    r = client.post(f"/api/investigations/{inv_id}/fixes/0/simulate", json={"seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert captured["metric"] == "spend" and captured["direction"] == "decrease"
    assert "block_sellers" in captured["changes"]
    assert body["pacing"]["after"]["active_days"] == 14

    # explicit request override wins over the fix's own target
    r2 = client.post(f"/api/investigations/{inv_id}/fixes/0/simulate",
                     json={"seed": 1, "target_direction": "increase"})
    assert r2.status_code == 200
    assert captured["direction"] == "increase"
