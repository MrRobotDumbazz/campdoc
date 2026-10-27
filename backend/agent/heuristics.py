"""Deterministic rule-based diagnostic engine (PRD §8 failure-mode library).

Runs over tool results collected by the runner. Doubles as:
- offline mode when Muse Spark env credentials are absent (demo/dev),
- baseline for evals,
- generator of candidate hypotheses (LLM mode can rank/extend them later).

Every rule emits findings whose evidence refs point at tool results that
were actually executed (enforced downstream in findings.enforce_evidence).
"""
from __future__ import annotations

from typing import Any

from .findings import Evidence, Finding

# share thresholds: below -> "low volume" signal
LOW_BID_VOLUME_RATIO = 0.5
CONCENTRATION_SHARE = 0.5
EARLY_EXHAUST_SPEND_SHARE = 0.9
BAD_SELLER_SPEND_SHARE = 0.5
HEALTHY_SPEND_PACE_MIN = 0.85


def _ev(ref: str, summary: str) -> Evidence:
    tool = ref.split(":", 1)[0]
    return Evidence(tool=tool, ref=ref, summary=summary)


def analyze(ctx: dict[str, Any], campaign_id: str) -> list[Finding]:
    findings: list[Finding] = []
    settings = (ctx.get("settings") or {}).get("data") or {}
    daily = (ctx.get("delivery_day") or {}).get("data") or {}
    hourly = (ctx.get("delivery_hour") or {}).get("data") or {}
    bids_outcome = ctx.get("bids_outcome") or {}
    bids_seller = ctx.get("bids_seller") or {}
    bench = (ctx.get("benchmark") or {}).get("data") or {}

    totals = daily.get("totals", {})
    shares = _outcome_shares(bids_outcome)
    med_gap = shares.get("_median_loss_gap")

    budget = float(settings.get("budget_total", 0)) if settings else 0.0
    spend = float(totals.get("spend", 0)) or 0.0
    spend_pace = spend / budget if budget else 0.0
    win_rate = shares.get("win", 0.0)
    outbid = shares.get("loss_outbid", 0.0)
    below_floor = shares.get("loss_below_floor", 0.0)
    freq_drop = shares.get("dropped_freq_cap", 0.0)
    targ_drop = shares.get("dropped_targeting", 0.0)

    # 1. Bid too low vs market
    if outbid > 0.35 and (med_gap is None or med_gap > 0):
        gap = f" median gap ${med_gap}" if med_gap is not None else ""
        findings.append(Finding(
            cause="Bid is below the market: most losses are outbids with winning prices above our bid",
            evidence=[
                _ev(f"query_bid_samples:{campaign_id}:outcome",
                    f"loss_outbid share {outbid:.0%} of sampled requests{gap}"),
                _ev(f"get_campaign_settings:{campaign_id}",
                    f"current bid ${settings.get('bid')}, strategy {settings.get('bid_strategy')}"),
            ],
            confidence=min(0.55 + outbid, 0.95),
            proposed_changes=[
                "Raise the bid by 20% to cross the competitor price distribution",
                "Switch to a goal-based bid strategy",
            ],
            changes=[{"bid_delta_pct": 20}, {"bid_delta_pct": 20}],
        ))

    # 6. Floor price conflicts
    if below_floor > 0.35 and below_floor >= outbid:
        conf = 0.7 + 0.25 * min((below_floor - 0.35) / 0.65, 1.0)
        findings.append(Finding(
            cause="Floor price conflicts: bids are rejected below publisher floors on most requests",
            evidence=[
                _ev(f"query_bid_samples:{campaign_id}:outcome",
                    f"loss_below_floor share {below_floor:.0%} of sampled requests"),
            ],
            confidence=conf,
            proposed_changes=[
                "Raise the bid above typical floors (+25%)",
                "Block high-floor sellers and redistribute",
            ],
            changes=[{"bid_delta_pct": 25}, {"block_sellers": _top_floor_sellers(bids_seller)}],
        ))

    # 3. Frequency cap too strict
    if freq_drop > 0.20:
        findings.append(Finding(
            cause="Frequency cap is too strict: a large share of eligible requests is dropped by the cap",
            evidence=[
                _ev(f"query_bid_samples:{campaign_id}:outcome",
                    f"dropped_freq_cap share {freq_drop:.0%} of sampled requests"),
                _ev(f"get_campaign_settings:{campaign_id}",
                    f"current frequency cap {settings.get('frequency_cap', {}).get('per_day')}/day"),
            ],
            confidence=min(0.55 + freq_drop, 0.95),
            proposed_changes=["Relax the frequency cap to 5 per day"],
            changes=[{"frequency_cap": 5}],
        ))

    # 2. Targeting too narrow
    bench_ratio = bench.get("ratio_vs_benchmark")
    bids_total = int(totals.get("bids", 0)) or None
    if bench_ratio is not None and bids_total is not None and bench_ratio < LOW_BID_VOLUME_RATIO and win_rate > 0.7:
        findings.append(Finding(
            cause="Targeting is too narrow: bid-request volume is far below benchmark while win rate is high",
            evidence=[
                _ev(f"compare_to_benchmark:{campaign_id}:impressions",
                    f"bid volume ratio vs healthy control: {bench_ratio:.2f}"),
                _ev(f"query_bid_samples:{campaign_id}:outcome",
                    f"win share {win_rate:.0%} (little competition inside narrow targeting)"),
                _ev(f"get_campaign_settings:{campaign_id}",
                    f"geo={len(settings['targeting']['geo'])}, audience={len(settings['targeting']['audience'])}"),
            ],
            confidence=0.85,
            proposed_changes=["Widen geo targeting to neighbouring states",
                              "Add one broader audience segment"],
            changes=[{"geo_widen": ["US-MA", "US-NJ", "US-PA"]},
                     {"audience_widen": ["lookalike_5pct"]}],
        ))

    # 4. Daypart/schedule mismatch
    top4 = hourly.get("top4_impressions_share")
    if top4 is not None and top4 > CONCENTRATION_SHARE and spend_pace < HEALTHY_SPEND_PACE_MIN:
        findings.append(Finding(
            cause="Dayparting is too restrictive: delivery concentrates in a few hours and budget stays unspent",
            evidence=[
                _ev(f"query_delivery:{campaign_id}:hour",
                    f"top-4 hours carry {top4:.0%} of impressions"),
                _ev(f"query_delivery:{campaign_id}:day",
                    f"spend ${spend:,.0f} of ${budget:,.0f} ({spend_pace:.0%} of budget)"),
                _ev(f"get_campaign_settings:{campaign_id}",
                    f"dayparts={settings.get('dayparts')}"),
            ],
            confidence=0.85,
            proposed_changes=["Widen dayparts to 00-08 and 18-23 in addition to current windows"],
            changes=[{"dayparts": ["00-08", "18-23"]}],
        ))

    # 5. Overspend from aggressive pacing
    if settings and settings.get("pacing") == "asap" and spend_pace > EARLY_EXHAUST_SPEND_SHARE and settings.get("flight_end"):
        findings.append(Finding(
            cause="Aggressive pacing (ASAP) exhausts the budget early in the flight",
            evidence=[
                _ev(f"get_campaign_settings:{campaign_id}",
                    f"pacing={settings.get('pacing')}, daily_budget_cap={settings.get('daily_budget_cap')}"),
                _ev(f"query_delivery:{campaign_id}:day",
                    f"last-day impressions collapsed to {daily.get('last_day_impressions')} "
                    f"vs first-day {daily.get('first_day_impressions')}"),
            ],
            confidence=0.9,
            proposed_changes=["Switch to even pacing with a daily budget cap"],
            changes=[{"pacing": "even", "daily_budget_cap": round(budget / 14, 2)}],
        ))

    # 7. Low-quality supply path
    bad = _bad_sellers(bids_seller)
    if bad:
        findings.append(Finding(
            cause="Spend concentrates on low-quality cheap-floor sellers (supply-path quality issue)",
            evidence=[
                _ev(f"query_bid_samples:{campaign_id}:seller",
                    f"sellers {', '.join(bad['sellers'])} carry {bad['share']:.0%} of estimated spend "
                    f"with median floor ${bad['floor']} (below campaign norm)"),
            ],
            confidence=0.85,
            proposed_changes=["Block the worst sellers and redistribute spend"],
            changes=[{"block_sellers": bad["sellers"]}],
        ))

    # 8. Healthy control: say so, do not invent problems
    if not findings:
        findings.append(Finding(
            cause="No major issue detected: delivery, win rate and pacing are within healthy bounds",
            evidence=[
                _ev(f"query_delivery:{campaign_id}:day",
                    f"spend ${spend:,.0f} of ${budget:,.0f} ({spend_pace:.0%} pace)"),
                _ev(f"query_bid_samples:{campaign_id}:outcome",
                    f"win share {win_rate:.0%}, outbids {outbid:.0%}, below-floor {below_floor:.0%}"),
            ],
            confidence=0.9,
            proposed_changes=[],
            changes=[],
        ))
    findings.sort(key=lambda f: -f.confidence)
    return findings


def _outcome_shares(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data", {}) if isinstance(result, dict) else {}
    if data.get("group_by") == "outcome":
        # rebuild overall shares from per-outcome group counts
        shares: dict[str, Any] = {}
        gaps: list[float] = []
        raw = data.get("groups", {})
        n_all = sum(g.get("n", 0) for g in raw.values())
        for key, g in raw.items():
            if n_all:
                shares[key] = g.get("n", 0) / n_all
            gaps.append(g.get("median_loss_gap_usd") or 0.0)
        if gaps:
            shares["_median_loss_gap"] = sorted(gaps)[len(gaps) // 2]
        return shares
    return {}


def _top_floor_sellers(bids_seller: dict[str, Any]) -> list[str]:
    groups = (bids_seller.get("data", {}).get("groups", {})) if isinstance(bids_seller, dict) else {}
    sellers = [s for s, g in groups.items() if (g.get("median_floor") or 0) >= 2.2]
    return sorted(sellers)[:3] or sorted(groups)[:3]


def _bad_sellers(bids_seller: dict[str, Any]) -> dict[str, Any] | None:
    """Supply-path signal: top sellers by spend share whose floors are well below
    the campaign norm (cheap remnant inventory eating the budget)."""
    groups = (bids_seller.get("data", {}).get("groups", {})) if isinstance(bids_seller, dict) else {}
    if len(groups) < 2:
        return None
    floors = sorted(g.get("median_floor") or 0 for g in groups.values())
    overall_floor = floors[len(floors) // 2]
    by_spend = sorted(groups.items(), key=lambda kv: -(kv[1].get("estimated_spend_share") or 0))
    top = by_spend[:2]
    top_share = sum(g.get("estimated_spend_share") or 0 for _, g in top)
    if top_share < BAD_SELLER_SPEND_SHARE:
        return None
    cheap = [(s, g) for s, g in top
             if overall_floor and (g.get("median_floor") or 0) <= overall_floor * 0.85]
    if not cheap:
        return None
    return {
        "sellers": sorted(s for s, _ in cheap),
        "share": top_share,
        "floor": min(g.get("median_floor") or 0 for _, g in cheap),
    }
