#!/usr/bin/env python3
"""Campaign Doctor — auction simulator v0 (ML zone, S-1 acting).

Implements /contracts/simulation.api.yaml v1-draft.
Method: deterministic replay of bid_samples.csv under modified settings
(first/second price from campaign settings) with pacing and constraint layers.
Assumptions and limits — simulator/README.md; a limitation note ships with every result.
"""
from __future__ import annotations

import csv
import json
import math
import random
from datetime import date
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "datasets"
LIMITATION_NOTE = "Simulation on a sample of bid requests; a forecast, not a guarantee"
NOT_MODELLED = ["audience_widen: not modelled in v0 (no audience dimension in the data)"]
FREQ_DROP_BASE = 0.93  # reach-recovery model: drop(C) = FREQ_DROP_BASE * C_old / C
HOURLY_SLACK = 1.1     # pacing-plan slack — the same constant as in data/generate.py


def _hours_from(dayparts) -> set[int]:
    if not dayparts:
        return set(range(24))
    out: set[int] = set()
    for p in dayparts:
        a, b = str(p).split("-")
        out.update(range(int(a), int(b)))
    return out


def _load(campaign_id: str, data_root: Path):
    cdir = Path(data_root) / campaign_id
    settings = json.loads((cdir / "campaign_settings.json").read_text(encoding="utf-8"))
    with (cdir / "bid_samples.csv").open(encoding="utf-8") as f:
        samples = list(csv.DictReader(f))
    with (cdir / "delivery_hourly.csv").open(encoding="utf-8") as f:
        hourly = list(csv.DictReader(f))
    for r in samples:
        r["floor_price"] = float(r["floor_price"])
        r["our_bid"] = float(r["our_bid"])
        r["winning_price"] = float(r["winning_price"])
        r["hour"] = int(r["ts"][11:13])
        r["day"] = r["ts"][:10]
    for r in hourly:
        r["bids"] = int(r["bids"])
        r["impressions"] = int(r["impressions"])
        r["spend"] = float(r["spend"])
    return settings, samples, hourly


def _drop_rate(cap_new, cap_old) -> float:
    if cap_new is None:
        return 0.0
    if cap_old is None:
        return 0.0
    if cap_new <= 0:
        return FREQ_DROP_BASE
    return min(FREQ_DROP_BASE * cap_old / cap_new, 1.0)


def _replay(settings, samples, scale, changes, budget_cap, seed):
    bid = settings["bid"]
    if changes.get("bid") is not None:
        bid = float(changes["bid"])
    elif changes.get("bid_delta_pct") is not None:
        bid *= 1 + float(changes["bid_delta_pct"]) / 100
    bid = round(bid, 4)

    geo = set(settings["targeting"]["geo"]) | set(changes.get("geo_widen") or [])
    blocked = set(changes.get("block_sellers") or [])
    dayparts = changes.get("dayparts", settings.get("dayparts"))
    hours = _hours_from(dayparts)
    pacing = changes.get("pacing") or settings["pacing"]
    cap_old = settings["frequency_cap"]["per_day"]
    cap_new = changes["frequency_cap"] if "frequency_cap" in changes else cap_old
    drop_new = _drop_rate(cap_new, cap_old)
    drop_old = _drop_rate(cap_old, cap_old) if cap_old is not None else 0.0
    # share of previously dropped requests that return under the new cap:
    # with the cap unchanged drop_new == drop_old -> recovery 0 (calibration holds)
    recovery = 1.0 if drop_old <= 0 else min(1.0, max(0.0, 1 - drop_new / drop_old))
    rng = random.Random(f"{settings['campaign_id']}:{seed}")

    days = (date.fromisoformat(settings["flight_end"])
            - date.fromisoformat(settings["flight_start"])).days + 1
    budget = budget_cap if budget_cap is not None else settings["budget_total"]
    daily_cap = changes.get("daily_budget_cap") or settings.get("daily_budget_cap")

    s_budget = budget / scale
    s_hour_allow = (budget / (days * 24) * HOURLY_SLACK / scale
                    if pacing == "even" else None)
    s_daily_cap = (daily_cap / scale) if daily_cap else None

    first_price = settings["auction_model"] == "first_price"

    def eligible(row):
        """Deterministic filters (shared by both passes)."""
        return (row["seller"] not in blocked
                and row["hour"] in hours
                and row["geo"] in geo)

    def pay_of(row):
        """Payment on a win at the new bid (0 — not a win)."""
        if bid < row["floor_price"] or bid <= row["winning_price"]:
            return 0.0
        return round(bid if first_price else max(row["floor_price"],
                                                 row["winning_price"]), 4)

    # Pass 1: unconstrained natural spend per DAY -> thinning factor.
    # Day level (not hour): at sample scale an hour holds 0-3 potential wins,
    # and an hour-level min-clamp systematically underspends; days are denser.
    natural: dict[str, float] = {}
    for row in samples:
        if not eligible(row):
            continue
        pay = pay_of(row)
        if pay <= 0:
            continue
        w = recovery if row["outcome"] == "dropped_freq_cap" else 1.0
        if w <= 0:
            continue
        natural[row["day"]] = natural.get(row["day"], 0.0) + pay * w
    day_allow = (s_hour_allow * len(hours)
                 if s_hour_allow is not None else None)
    # global systematic factor (Bresenham): keeps exactly floor(N*f) wins,
    # evenly spread across flight positions — exact count with zero variance
    # and no per-day floor losses; E[spend] = the pacing plan
    total_natural = sum(natural.values())
    thin_f = (min(1.0, (day_allow * len(natural)) / total_natural)
              if day_allow is not None and total_natural > 0 else 1.0)

    # Pass 2: replay. Wins are thinned systematically (a global counter):
    # floor((i+1)*f) > floor(i*f) — evenly along the flight; no rng needed
    win_idx = 0
    wins = bids = 0
    spend = 0.0
    seller_spend: dict[str, float] = {}
    hours_active: set[int] = set()
    days_active: set[str] = set()
    budget_left = s_budget
    day_spent: dict[str, float] = {}

    for row in samples:
        if not eligible(row):
            continue
        if row["outcome"] == "dropped_freq_cap" and rng.random() > recovery:
            continue
        # dropped_targeting / dropped_schedule / no_bid_budget re-enter
        # the auction: their fate is decided by the filters and pacing gates
        if budget_left <= 0:
            continue
        pay = pay_of(row)
        if pay > 0:
            i = win_idx
            win_idx += 1
            if math.floor((i + 1) * thin_f) <= math.floor(i * thin_f):
                continue  # pacing: the hour/flight plan is exhausted in expectation

        bids += 1
        if pay <= 0:
            continue
        if s_daily_cap is not None and day_spent.get(row["day"], 0.0) + pay > s_daily_cap:
            continue
        if pay > budget_left:
            continue  # hard global cap: the budget is never exceeded
        wins += 1
        spend += pay
        day_spent[row["day"]] = day_spent.get(row["day"], 0.0) + pay
        budget_left -= pay
        seller_spend[row["seller"]] = seller_spend.get(row["seller"], 0.0) + pay
        hours_active.add(row["hour"])
        days_active.add(row["day"])

    impressions = wins * scale
    spend_total = spend * scale
    win_rate = round(wins / bids, 4) if bids else 0.0
    ecpm = round(spend / wins * 1000, 4) if wins else 0.0
    top_seller = (max(seller_spend.values()) / spend) if spend else 0.0
    return {
        "impressions": int(round(impressions)),
        "spend": round(spend_total, 2),
        "win_rate": win_rate,
        "ecpm": ecpm,
        "_diag": {
            "bids_sample": bids, "wins_sample": wins,
            "active_hours": len(hours_active), "active_days": len(days_active),
            "top_seller_spend_share": round(top_seller, 4),
            "budget_utilization": round(spend_total / budget, 4) if budget else 0.0,
        },
    }


def run_simulation(inp: dict, data_root=None) -> dict:
    """Contract entry point: input → output (see /contracts/simulation.api.yaml)."""
    data_root = Path(data_root) if data_root else DATA_ROOT
    settings, samples, hourly = _load(inp["campaign_id"], data_root)
    seed = int(inp.get("seed", 42))

    sample_bids = sum(1 for r in samples
                      if r["outcome"] in ("win", "loss_outbid", "loss_below_floor"))
    actual_bids = sum(r["bids"] for r in hourly)
    scale = actual_bids / sample_bids if sample_bids else 1.0

    changes = inp.get("changes") or {}
    constraints = inp.get("constraints") or {}
    target = inp.get("target_metric", "impressions")
    direction = inp.get("target_direction", "increase")
    threshold = float(inp.get("threshold_pct", 5.0))

    before = _replay(settings, samples, scale, {}, None, seed)
    after = _replay(settings, samples, scale, changes,
                    constraints.get("budget_cap_total"), seed)
    delta = {k: round(after[k] - before[k], 4) for k in
             ("impressions", "spend", "win_rate", "ecpm")}

    violated = []
    max_ecpm = constraints.get("max_ecpm")
    if max_ecpm is not None and after["ecpm"] > float(max_ecpm):
        violated.append(f"max_ecpm: after={after['ecpm']} > cap={max_ecpm}")
    budget_cap = constraints.get("budget_cap_total")
    if budget_cap is not None and after["spend"] > float(budget_cap) * 1.001:
        violated.append(f"budget_cap_total: after={after['spend']} > cap={budget_cap}")

    base = before[target] or 1
    gain = ((after[target] - before[target]) if direction != "decrease"
            else (before[target] - after[target]))
    improves = gain / abs(base) >= threshold / 100
    verified = bool(improves and not violated)

    def pacing_view(m):
        d = m["_diag"]
        return {"active_days": d["active_days"], "active_hours": d["active_hours"],
                "budget_utilization": d["budget_utilization"]}

    notes = [LIMITATION_NOTE, *NOT_MODELLED,
             f"freq-recovery model: drop(C)={FREQ_DROP_BASE}*C_old/C",
             f"pacing before: hours={before['_diag']['active_hours']}, "
             f"days={before['_diag']['active_days']}, "
             f"budget_util={before['_diag']['budget_utilization']}",
             f"pacing after: hours={after['_diag']['active_hours']}, "
             f"days={after['_diag']['active_days']}, "
             f"budget_util={after['_diag']['budget_utilization']}",
             f"top-seller spend share before/after: "
             f"{before['_diag']['top_seller_spend_share']}/"
             f"{after['_diag']['top_seller_spend_share']}"]

    return {
        "before": {k: before[k] for k in ("impressions", "spend", "win_rate", "ecpm")},
        "after": {k: after[k] for k in ("impressions", "spend", "win_rate", "ecpm")},
        "delta": delta,
        "verified": verified,
        "threshold_pct": threshold,
        "violated_constraints": violated,
        "pacing": {"before": pacing_view(before), "after": pacing_view(after)},
        "notes": notes,
    }
