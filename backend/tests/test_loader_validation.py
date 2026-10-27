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
