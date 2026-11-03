import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulator.server import make_handler  # noqa: E402


@pytest.fixture(scope="module")
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                make_handler(Path(__file__).parents[2] / "data"
                                             / "datasets"))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _post(url, payload):
    req = urllib.request.Request(
        url + "/simulate", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health(base_url):
    with urllib.request.urlopen(base_url + "/health", timeout=5) as r:
        body = json.loads(r.read())
    assert body["status"] == "ok"
    assert "simulation.api.yaml" in body["contract"]


def test_simulate_contract_shape(base_url):
    code, out = _post(base_url, {"campaign_id": "fm1_bid_low", "seed": 42,
                                 "changes": {"bid": 2.6}})
    assert code == 200
    for k in ("before", "after", "delta", "verified", "threshold_pct",
              "violated_constraints", "notes"):
        assert k in out, k
    assert out["verified"] is True


def test_simulate_deterministic_over_http(base_url):
    _, a = _post(base_url, {"campaign_id": "fm1_bid_low", "seed": 42,
                            "changes": {"bid": 2.6}})
    _, b = _post(base_url, {"campaign_id": "fm1_bid_low", "seed": 42,
                            "changes": {"bid": 2.6}})
    assert a == b


def test_bad_request_and_unknown_campaign(base_url):
    code, out = _post(base_url, {"seed": 42})
    assert code == 400 and out["error"] == "bad_request"
    code, out = _post(base_url, {"campaign_id": "no_such", "seed": 42})
    assert code == 404 and out["error"] == "unknown_campaign"
