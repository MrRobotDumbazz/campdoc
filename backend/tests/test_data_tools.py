"""Unit tests for the four data tools (PRD 6.2) incl. error messages."""
from __future__ import annotations

import pytest

from backend.tools import data_tools
from backend.tools.base import ToolError
from backend.tools.loader import DatasetRepository


@pytest.fixture()
def repo(tmp_path):
    return DatasetRepository(tmp_path / "no-data")


def test_query_delivery_day_and_filters(repo):
    r = data_tools.query_delivery(repo, "camp_001_bid_low", group_by="day")
    assert r.tool == "query_delivery" and r.ref.endswith(":day")
    assert r.data["totals"]["impressions"] > 0
    dates = sorted(r.data["daily_impressions"])
    r2 = data_tools.query_delivery(repo, "camp_001_bid_low", group_by="day",
                                   date_from=dates[0], date_to=dates[0])
    assert len(r2.data["daily_impressions"]) == 1


def test_query_delivery_hour_concentration(repo):
    r = data_tools.query_delivery(repo, "camp_004_daypart", group_by="hour")
    assert set(r.data["top4_hours"]) <= set(range(24))
    assert 0 < r.data["top4_impressions_share"] <= 1


def test_query_delivery_bad_args(repo):
    with pytest.raises(ToolError) as e:
        data_tools.query_delivery(repo, "camp_001_bid_low", group_by="week")
    assert "group_by" in str(e.value)
    with pytest.raises(ToolError):
        data_tools.query_delivery(repo, "camp_001_bid_low", date_from="not-a-date")
    with pytest.raises(ToolError):
        data_tools.query_delivery(repo, "ghost")


def test_query_bid_samples_groups_and_filter(repo):
    r = data_tools.query_bid_samples(repo, "camp_001_bid_low", group_by="outcome")
    assert {"win", "loss_outbid"} <= set(r.data["groups"])
    wins = data_tools.query_bid_samples(repo, "camp_001_bid_low", group_by="seller",
                                        outcome="win")
    assert all(g["n"] > 0 for g in wins.data["groups"].values())
    with pytest.raises(ToolError) as e:
        data_tools.query_bid_samples(repo, "camp_001_bid_low", outcome="WON")
    assert "outcome" in str(e.value)
    with pytest.raises(ToolError):
        data_tools.query_bid_samples(repo, "camp_001_bid_low", group_by="os")


def test_get_campaign_settings_shape(repo):
    r = data_tools.get_campaign_settings(repo, "control_healthy")
    s = r.data
    assert s["pacing"] in ("even", "asap")
    assert s["auction_model"] in ("first_price", "second_price")
    assert {"geo", "audience", "inventory"} <= set(s["targeting"])


def test_compare_to_benchmark(repo):
    r = data_tools.compare_to_benchmark(repo, "camp_002_narrow", metric="impressions")
    assert r.data["benchmark_campaign"] == "control_healthy"
    assert r.data["ratio_vs_benchmark"] < 0.5  # narrow campaign vs control
    with pytest.raises(ToolError):
        data_tools.compare_to_benchmark(repo, "control_healthy")
    with pytest.raises(ToolError) as e:
        data_tools.compare_to_benchmark(repo, "camp_001_bid_low", metric="ctr")
    assert "Unknown metric" in str(e.value)
