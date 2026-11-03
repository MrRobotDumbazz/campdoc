"""Schema validation per /contracts/data.schemas.md: clear, human-readable errors."""
from __future__ import annotations

import json

import pytest

from backend.tools.base import ToolError
from backend.tools.loader import (DataValidationError, DatasetRepository,
                                  _load_bid_samples, _load_csv,
                                  SCHEMA_DELIVERY_DAILY)


def _write(p, lines):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


GOOD_DAILY = [
    "date,impressions,spend,bids,wins",
    "2026-10-20,41200,318.44,2100000,41200",
    "2026-10-21,40010,309.20,2050000,40010",
]


def test_missing_column_named_in_error(tmp_path):
    f = tmp_path / "delivery_daily.csv"
    _write(f, ["date,impressions,spend,bids", "2026-10-20,10,1.0,100"])
    with pytest.raises(DataValidationError) as e:
        _load_csv(f, SCHEMA_DELIVERY_DAILY)
    assert "wins" in str(e.value)
    assert "missing required column" in str(e.value).lower()


def test_bad_row_value_named_in_error(tmp_path):
    f = tmp_path / "delivery_daily.csv"
    _write(f, ["date,impressions,spend,bids,wins", "2026-10-20,-5,1.0,100,10"])
    with pytest.raises(DataValidationError) as e:
        _load_csv(f, SCHEMA_DELIVERY_DAILY)
    assert "impressions negative" in str(e.value)


def test_bid_samples_bad_enum(tmp_path):
    f = tmp_path / "bid_samples.csv"
    _write(f, [
        "ts,site_app,seller,geo,device,floor_price,our_bid,winning_price,outcome",
        "2026-10-20T14:03:11Z,app_412,ssp_7,US-NY,mobile,2.10,1.85,2.30,WON",
    ])
    with pytest.raises(DataValidationError) as e:
        _load_bid_samples(f)
    assert "outcome" in str(e.value)


def test_bid_samples_accepts_v01_outcomes(tmp_path):
    """data.schemas v0.1: no_bid_budget and dropped_schedule are valid outcomes."""
    f = tmp_path / "bid_samples.csv"
    _write(f, [
        "ts,site_app,seller,geo,device,floor_price,our_bid,winning_price,outcome",
        "2026-10-20T14:03:11Z,app_412,ssp_7,US-NY,mobile,2.10,1.85,2.30,no_bid_budget",
        "2026-10-20T14:03:12Z,app_412,ssp_7,US-NY,mobile,2.10,1.85,2.30,dropped_schedule",
    ])
    samples = _load_bid_samples(f)
    assert [s.outcome for s in samples] == ["no_bid_budget", "dropped_schedule"]


def test_data_dir_campaign_ok(tmp_path):
    camp = tmp_path / "data" / "camp_x"
    _write(camp / "delivery_daily.csv", GOOD_DAILY)
    _write(camp / "delivery_hourly.csv",
           ["date,hour,impressions,spend,bids,wins",
            "2026-10-20,0,100,7.7,5100,100"] * 1)
    _write(camp / "bid_samples.csv",
           ["ts,site_app,seller,geo,device,floor_price,our_bid,winning_price,outcome",
            "2026-10-20T14:03:11Z,app_412,ssp_7,US-NY,mobile,2.10,1.85,2.30,win"])
    (camp / "campaign_settings.json").write_text(json.dumps({
        "campaign_id": "camp_x", "budget_total": 1000, "flight_start": "2026-10-20",
        "flight_end": "2026-10-21", "pacing": "even", "daily_budget_cap": None,
        "bid": 1.85, "bid_strategy": "fixed",
        "targeting": {"geo": ["US-NY"], "audience": ["a"], "inventory": ["i"]},
        "frequency_cap": {"per_day": 5}, "dayparts": None, "auction_model": "second_price",
    }), encoding="utf-8")
    repo = DatasetRepository(tmp_path / "data")
    ds = repo.get("camp_x")
    assert ds.source == "data-dir"
    assert ds.daily[0]["impressions"] == 41200


def test_unknown_campaign_error_lists_known(tmp_path):
    repo = DatasetRepository(tmp_path / "empty")
    with pytest.raises(ToolError) as e:
        repo.get("ghost")
    assert "Unknown campaign_id" in str(e.value)
    assert "control_healthy" in str(e.value)


SETTINGS_JSON = {
    "campaign_id": "camp_x", "budget_total": 1000, "flight_start": "2026-10-20",
    "flight_end": "2026-10-21", "pacing": "even", "daily_budget_cap": None,
    "bid": 1.85, "bid_strategy": "fixed",
    "targeting": {"geo": ["US-NY"], "audience": ["a"], "inventory": ["i"]},
    "frequency_cap": {"per_day": 5}, "dayparts": None, "auction_model": "second_price",
}


def _make_campaign(root, cid, mode_key="mode", mode=3):
    camp = root / cid
    _write(camp / "delivery_daily.csv", GOOD_DAILY)
    _write(camp / "delivery_hourly.csv",
           ["date,hour,impressions,spend,bids,wins", "2026-10-20,0,100,7.7,5100,100"])
    _write(camp / "bid_samples.csv",
           ["ts,site_app,seller,geo,device,floor_price,our_bid,winning_price,outcome",
            "2026-10-20T14:03:11Z,app_412,ssp_7,US-NY,mobile,2.10,1.85,2.30,win"])
    s = dict(SETTINGS_JSON, campaign_id=cid)
    (camp / "campaign_settings.json").write_text(json.dumps(s), encoding="utf-8")
    return {"name": cid, mode_key: mode}


def test_data_dir_skips_non_campaign_subdirs(tmp_path):
    """Subdirectories without campaign_settings.json (e.g. __pycache__) are skipped."""
    root = tmp_path / "data"
    _make_campaign(root, "camp_x")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "junk.pyc").write_text("not a campaign")
    repo = DatasetRepository(root)
    assert [c["campaign_id"] for c in repo.list_campaigns()] == ["camp_x"]


def test_manifest_mode_key_used_for_ground_truth_and_healthy(tmp_path):
    root = tmp_path / "data"
    camps = {"camp_x": _make_campaign(root, "camp_x", mode=3),
             "control_healthy": _make_campaign(root, "control_healthy", mode=0)}
    (root / "manifest.json").write_text(json.dumps({"campaigns": camps}), encoding="utf-8")
    repo = DatasetRepository(root)
    assert repo.get("camp_x").ground_truth_mode == 3
    assert repo.get("camp_x").healthy is False
    assert repo.get("control_healthy").ground_truth_mode == 0
    assert repo.get("control_healthy").healthy is True


def test_manifest_legacy_failure_mode_fallback(tmp_path):
    root = tmp_path / "data"
    camps = {"camp_old": _make_campaign(root, "camp_old", mode_key="failure_mode", mode=6)}
    (root / "manifest.json").write_text(json.dumps({"campaigns": camps}), encoding="utf-8")
    repo = DatasetRepository(root)
    assert repo.get("camp_old").ground_truth_mode == 6
