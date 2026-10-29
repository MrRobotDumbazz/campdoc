import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulator.simulate import run_simulation  # noqa: E402

CID = {
    0: "control_healthy", 1: "fm1_bid_low", 2: "fm2_narrow", 3: "fm3_freqcap",
    4: "fm4_daypart", 5: "fm5_asap", 6: "fm6_floor", 7: "fm7_supply",
}


def run(cid, **kw):
    inp = {"campaign_id": cid, "seed": 42}
    inp.update(kw)
    return run_simulation(inp)


def agg_hourly(cid):
    root = Path(__file__).resolve().parents[2] / "data" / "datasets" / cid
    import csv
    with (root / "delivery_hourly.csv").open() as f:
        rows = list(csv.DictReader(f))
    return (sum(int(r["impressions"]) for r in rows),
            round(sum(float(r["spend"]) for r in rows), 2))


def test_output_schema():
    out = run("control_healthy")
    for k in ["before", "after", "delta", "verified", "threshold_pct",
              "violated_constraints", "notes"]:
        assert k in out, k
    for part in ("before", "after"):
        assert set(out[part]) == {"impressions", "spend", "win_rate", "ecpm"}
    assert any("не гарантия" in n for n in out["notes"])


def test_determinism():
    a = run("fm1_bid_low", changes={"bid": 2.6})
    b = run("fm1_bid_low", changes={"bid": 2.6})
    assert a == b


def test_calibration_healthy():
    out = run("control_healthy")
    imps, spend = agg_hourly("control_healthy")
    assert abs(out["before"]["impressions"] - imps) / imps < 0.15
    assert abs(out["before"]["spend"] - spend) / spend < 0.15


def test_calibration_asap_early_exhaust():
    out = run("fm5_asap")
    imps, _ = agg_hourly("fm5_asap")
    assert abs(out["before"]["impressions"] - imps) / imps < 0.15


def test_calibration_daypart():
    out = run("fm4_daypart")
    imps, _ = agg_hourly("fm4_daypart")
    assert abs(out["before"]["impressions"] - imps) / imps < 0.15


def test_fm1_raise_bid():
    out = run("fm1_bid_low", changes={"bid": 2.6})
    assert out["after"]["impressions"] > out["before"]["impressions"] * 2
    assert out["verified"] is True


def test_fm2_widen_geo():
    out = run("fm2_narrow",
              changes={"geo_widen": ["US-NY", "US-CA", "US-TX", "US-FL", "US-IL"]})
    assert out["after"]["impressions"] > out["before"]["impressions"] * 1.4
    assert out["verified"] is True


def test_fm3_relax_freq_cap():
    out = run("fm3_freqcap", changes={"frequency_cap": 5})
    assert out["after"]["impressions"] > out["before"]["impressions"] * 1.5
    assert out["verified"] is True


def test_fm4_open_dayparts():
    out = run("fm4_daypart", changes={"dayparts": None})
    assert out["after"]["impressions"] > out["before"]["impressions"] * 1.5
    assert out["verified"] is True


def test_fm5_even_pacing_spreads():
    out = run("fm5_asap", changes={"pacing": "even", "daily_budget_cap": 20000 / 14})
    days = {p: int([n for n in out["notes"] if n.startswith(f"pacing {p}")][0]
                   .split("days=")[1].split(",")[0]) for p in ("before", "after")}
    assert days["before"] <= 4          # выгорание на старте
    assert days["after"] >= 12          # размазано на флайт
    assert out["after"]["spend"] <= 20000 * 1.001


def test_fm6_bid_above_floors():
    # честная экономика: над флорами платим дороже -> impressions не растут,
    # растёт доставка бюджета (spend) — target для FM6 именно spend
    out = run("fm6_floor", changes={"bid": 7.0}, target_metric="spend")
    assert out["after"]["spend"] > out["before"]["spend"] * 1.5
    assert out["verified"] is True


def test_fm7_block_seller_removes_concentration():
    out = run("fm7_supply", changes={"block_sellers": ["ssp_7"]})
    note = [n for n in out["notes"] if "top-seller" in n][0]
    after_share = note.split("/")[-1]
    assert float(after_share) < 0.35  # при 6 равных продавцах ~1/6; запас на шум выборки


def test_constraint_max_ecpm_blocks_verification():
    out = run("fm1_bid_low", changes={"bid": 3.5},
              constraints={"max_ecpm": 2.0})
    assert out["violated_constraints"]
    assert out["verified"] is False


def test_constraint_budget_cap_respected():
    out = run("fm6_floor", changes={"bid": 7.0},
              constraints={"budget_cap_total": 10000})
    assert out["after"]["spend"] <= 10000 * 1.001


def test_healthy_no_fake_improvement_needed():
    out = run("control_healthy", changes={"bid": 2.61})
    # микроскопенная правка не должна давать verified
    assert out["verified"] is False
