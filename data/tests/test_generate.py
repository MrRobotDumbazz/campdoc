import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate import SPECS, simulate  # noqa: E402

BY = {s.campaign_id: s for s in SPECS}


def sim(cid, seed=42):
    return simulate(BY[cid], seed)


def stats(cid, seed=42):
    return sim(cid, seed)["stats"]


def test_determinism():
    a = simulate(BY["control_healthy"], 42)
    b = simulate(BY["control_healthy"], 42)
    assert a["samples"] == b["samples"] and a["hourly"] == b["hourly"]
    c = simulate(BY["control_healthy"], 43)
    assert c["samples"] != a["samples"]


def test_settings_and_row_schemas():
    r = sim("control_healthy")
    s = r["settings"]
    for k in ["campaign_id", "budget_total", "flight_start", "flight_end", "pacing",
              "daily_budget_cap", "bid", "bid_strategy", "targeting", "frequency_cap",
              "dayparts", "auction_model"]:
        assert k in s, k
    assert set(r["hourly"][0]) >= {"date", "hour", "impressions", "spend", "bids", "wins"}
    assert set(r["samples"][0]) >= {"ts", "site_app", "seller", "geo", "device",
                                    "floor_price", "our_bid", "winning_price", "outcome"}
    assert r["hourly"] and r["samples"]


def test_healthy_control_delivers():
    st = stats("control_healthy")
    assert 0.90 <= st["delivery_ratio"] <= 1.02
    assert st["win_rate"] > 0.03
    assert st["freq_drop_share"] < 0.05
    assert st["below_floor_share"] < 0.1


def test_fm1_bid_low():
    h, f = stats("control_healthy"), stats("fm1_bid_low")
    assert f["win_rate"] < 0.5 * h["win_rate"]
    assert f["delivery_ratio"] < 0.5


def test_fm2_narrow():
    h, f = stats("control_healthy"), stats("fm2_narrow")
    assert f["bids"] < 0.5 * h["bids"]
    assert f["win_rate"] > 1.5 * h["win_rate"]
    assert f["delivery_ratio"] < 0.95


def test_fm3_freq_cap():
    st = stats("fm3_freqcap")
    assert st["freq_drop_share"] > 0.4
    assert st["delivery_ratio"] < 0.9


def test_fm4_daypart():
    st = stats("fm4_daypart")
    assert st["active_hours_per_day"] <= 9
    assert st["delivery_ratio"] < 0.5


def test_fm5_early_exhaust():
    st = stats("fm5_asap")
    assert st["delivery_ratio"] >= 0.99
    assert st["last_delivery_day"] < 10


def test_fm6_floor_conflicts():
    st = stats("fm6_floor")
    assert st["below_floor_share"] > 0.3
    assert st["delivery_ratio"] < 0.85


def test_fm7_supply_concentration():
    st = stats("fm7_supply")
    assert st["top_seller_spend_share"] > 0.5
