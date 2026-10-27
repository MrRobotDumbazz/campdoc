"""Data tools exposed to the agent (PRD 6.2):
query_delivery, query_bid_samples, get_campaign_settings, compare_to_benchmark.

Every tool returns a ToolResult whose `ref` can be cited as evidence.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date
from typing import Any

from .base import ToolError, ToolResult
from .loader import DatasetRepository

BENCHMARK_CAMPAIGN = "control_healthy"


def _parse_date(value: str, what: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"Invalid {what} '{value}': expected YYYY-MM-DD.")


def query_delivery(
    repo: DatasetRepository,
    campaign_id: str,
    metric: str | None = None,
    group_by: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ToolResult:
    ds = repo.get(campaign_id)
    group_by = group_by or "day"
    if group_by not in ("day", "hour"):
        raise ToolError(f"group_by must be 'day' or 'hour', got '{group_by}'.")
    rows = ds.hourly if group_by == "hour" else ds.daily
    d_from = _parse_date(date_from, "date_from") if date_from else None
    d_to = _parse_date(date_to, "date_to") if date_to else None
    rows = [r for r in rows
            if (d_from is None or r["date"] >= d_from.isoformat())
            and (d_to is None or r["date"] <= d_to.isoformat())]
    if not rows:
        raise ToolError(f"No delivery rows for {campaign_id} in range {date_from}..{date_to}.")

    totals = {
        "impressions": sum(r["impressions"] for r in rows),
        "spend": round(sum(r["spend"] for r in rows), 2),
        "bids": sum(r["bids"] for r in rows),
        "wins": sum(r["wins"] for r in rows),
    }
    if group_by == "hour":
        by_hour: dict[int, dict[str, float]] = defaultdict(lambda: {"impressions": 0, "n": 0})
        for r in rows:
            by_hour[r["hour"]]["impressions"] += r["impressions"]
            by_hour[r["hour"]]["n"] += 1
        top_hours = sorted(by_hour.items(), key=lambda kv: -kv[1]["impressions"])[:4]
        top4_share = (sum(v["impressions"] for _, v in top_hours)
                      / max(totals["impressions"], 1))
        detail = {
            "impressions_by_hour": {str(h): int(v["impressions"]) for h, v in sorted(by_hour.items())},
            "top4_hours": [h for h, _ in top_hours],
            "top4_impressions_share": round(top4_share, 4),
        }
    else:
        detail = {
            "daily_impressions": {r["date"]: r["impressions"] for r in rows},
            "first_day_impressions": rows[0]["impressions"],
            "last_day_impressions": rows[-1]["impressions"],
        }
    payload = {"campaign_id": campaign_id, "granularity": group_by, "totals": totals, **detail}
    summary = (f"{campaign_id} delivery ({group_by}): impressions={totals['impressions']:,} "
               f"spend=${totals['spend']:,} bids={totals['bids']:,} wins={totals['wins']:,}")
    if metric:
        if metric not in totals:
            raise ToolError(f"Unknown metric '{metric}'. Available: impressions, spend, bids, wins.")
        summary = f"{campaign_id} delivery ({group_by}) [{metric}]: {totals[metric]:,}"
    return ToolResult(tool="query_delivery", ref=f"query_delivery:{campaign_id}:{group_by}",
                      summary=summary, data=payload)


def query_bid_samples(
    repo: DatasetRepository,
    campaign_id: str,
    group_by: str | None = None,
    outcome: str | None = None,
    limit: int = 20,
) -> ToolResult:
    ds = repo.get(campaign_id)
    group_by = group_by or "outcome"
    if group_by not in ("outcome", "seller", "geo", "device"):
        raise ToolError(f"group_by must be one of outcome|seller|geo|device, got '{group_by}'.")
    if outcome is not None and outcome not in {"win", "loss_below_floor", "loss_outbid",
                                               "dropped_freq_cap", "dropped_targeting"}:
        raise ToolError(f"Unknown outcome filter '{outcome}'.")

    rows = [s for s in ds.bid_samples if outcome is None or s.outcome == outcome]
    if not rows:
        raise ToolError(f"No bid samples for {campaign_id} (filter outcome={outcome}).")
    n = len(rows)

    def _agg(items: list) -> dict[str, Any]:
        outcomes: dict[str, int] = defaultdict(int)
        for s in items:
            outcomes[s.outcome] += 1
        losses = [s for s in items if s.outcome in ("loss_outbid", "loss_below_floor")]
        gap = [round(s.winning_price - s.our_bid, 4) for s in losses] or [0.0]
        spend_share = None
        return {
            "n": len(items),
            "outcome_share": {k: round(v / len(items), 4) for k, v in sorted(outcomes.items())},
            "median_loss_gap_usd": round(statistics.median(gap), 4),
        }

    groups: dict[str, Any] = {}
    keyed: dict[str, list] = defaultdict(list)
    for s in rows:
        keyed[getattr(s, group_by)].append(s)
    for key, items in sorted(keyed.items()):
        g = _agg(items)
        if group_by == "seller":
            win_paid = [s.winning_price for s in items if s.outcome == "win"]
            g["estimated_spend_share"] = round(sum(win_paid) / max(
                sum(s.winning_price for s in rows if s.outcome == "win"), 1e-9), 4)
            g["median_floor"] = round(statistics.median([s.floor_price for s in items]), 4)
        groups[str(key)] = g

    top_group, top_g = max(groups.items(), key=lambda kv: kv[1]["n"])
    payload = {"campaign_id": campaign_id, "group_by": group_by, "filter_outcome": outcome,
               "n": n, "groups": groups}
    summary = (f"{campaign_id} bid samples by {group_by} (n={n}); "
               f"largest group '{top_group}': {top_g['outcome_share']}")
    return ToolResult(tool="query_bid_samples", ref=f"query_bid_samples:{campaign_id}:{group_by}",
                      summary=summary, data=payload)


def get_campaign_settings(repo: DatasetRepository, campaign_id: str) -> ToolResult:
    ds = repo.get(campaign_id)
    t = ds.settings["targeting"]
    fc = ds.settings["frequency_cap"]["per_day"]
    summary = (f"{campaign_id}: budget=${ds.settings['budget_total']:,.0f}, "
               f"flight {ds.settings['flight_start']}..{ds.settings['flight_end']}, "
               f"pacing={ds.settings['pacing']}, bid=${ds.settings['bid']}, "
               f"geo={len(t['geo'])}, audience={len(t['audience'])}, freq_cap={fc}/day, "
               f"dayparts={ds.settings['dayparts']}, auction={ds.settings['auction_model']}")
    return ToolResult(tool="get_campaign_settings", ref=f"get_campaign_settings:{campaign_id}",
                      summary=summary, data=ds.settings)


def compare_to_benchmark(repo: DatasetRepository, campaign_id: str,
                         metric: str = "impressions") -> ToolResult:
    ds = repo.get(campaign_id)
    if ds.campaign_id == BENCHMARK_CAMPAIGN:
        raise ToolError("control_healthy is itself the benchmark; compare a real campaign instead.")
    try:
        bench = repo.get(BENCHMARK_CAMPAIGN)
    except ToolError:
        raise ToolError(f"Benchmark campaign '{BENCHMARK_CAMPAIGN}' not available; cannot compare.")
    agg = {"impressions": lambda d: sum(r["impressions"] for r in d.daily),
           "spend": lambda d: round(sum(r["spend"] for r in d.daily), 2),
           "bids": lambda d: sum(r["bids"] for r in d.daily),
           "wins": lambda d: sum(r["wins"] for r in d.daily)}
    if metric not in agg:
        raise ToolError(f"Unknown metric '{metric}'. Available: {', '.join(agg)}.")
    value, bvalue = agg[metric](ds), agg[metric](bench)
    ratio = round(value / bvalue, 4) if bvalue else None
    payload = {"campaign_id": campaign_id, "metric": metric, "value": value,
               "benchmark_campaign": BENCHMARK_CAMPAIGN, "benchmark_value": bvalue,
               "ratio_vs_benchmark": ratio}
    summary = (f"{campaign_id} {metric}={value:,} vs benchmark {BENCHMARK_CAMPAIGN} "
               f"{metric}={bvalue:,} (ratio {ratio})")
    return ToolResult(tool="compare_to_benchmark", ref=f"compare_to_benchmark:{campaign_id}:{metric}",
                      summary=summary, data=payload)
