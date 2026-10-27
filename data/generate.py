#!/usr/bin/env python3
"""Campaign Doctor — генератор синтетических данных v0 (зона ML, S-1 acting).

Схемы: /contracts/data.schemas.md. Failure modes: PRD §8 (0=healthy control, 1..7).
Детерминизм: одинаковый seed -> идентичные файлы (покрыто тестом).
Запуск: python3 data/generate.py [--out data/datasets] [--seed 42]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

FLIGHT_START = "2026-10-12"
FLIGHT_DAYS = 14
GEOS = ["US-NY", "US-CA", "US-TX", "US-FL", "US-IL"]
DEVICES = ["mobile", "desktop", "ctv"]
SELLERS = [f"ssp_{i}" for i in range(1, 9)]
SITES = [f"app_{i * 111}" for i in range(1, 13)]
BASE_RPH = 800          # запросов в час у healthy
COMP_MEDIAN = 3.9       # рынок: топ-конкурент
COMP_SIGMA = 0.5
FLOOR_MEDIAN = 1.2
FLOOR_SIGMA = 0.4
HIGH_FLOOR_MEDIAN = 6.5
SAMPLE_KEEP = 0.02      # доля запросов, попадающих в bid_samples
NICHE_TRAFFIC = 0.6     # доля трафика «подозрительного» продавца (FM7)


@dataclass
class Spec:
    campaign_id: str
    name: str
    mode: int                      # 0 = healthy control; 1..7 = PRD §8
    bid: float = 2.60
    budget_total: float = 20000.0
    pacing: str = "even"           # even | asap
    freq_cap_per_day: int | None = None
    geo: tuple = tuple(GEOS)
    dayparts: tuple | None = None  # ("09-17",) = часы 9..16
    auction_model: str = "second_price"
    base_mult: float = 1.0
    comp_median: float = COMP_MEDIAN
    freq_drop: float = 0.0
    high_floor_share: float = 0.0
    niche_comp: tuple | None = None  # (seller, comp_median, comp_sigma)


SPECS = [
    Spec("control_healthy", "Healthy control", 0),
    Spec("fm1_bid_low", "FM1 bid too low vs market", 1, bid=1.40),
    Spec("fm2_narrow", "FM2 targeting too narrow", 2, base_mult=0.2,
         comp_median=2.2, geo=("US-NY",)),
    Spec("fm3_freqcap", "FM3 frequency cap too strict", 3,
         freq_drop=0.93, freq_cap_per_day=2),
    Spec("fm4_daypart", "FM4 daypart/schedule mismatch", 4, dayparts=("09-17",)),
    Spec("fm5_asap", "FM5 overspend aggressive pacing", 5,
         pacing="asap", auction_model="first_price"),
    Spec("fm6_floor", "FM6 floor price conflicts", 6, high_floor_share=0.93),
    Spec("fm7_supply", "FM7 low-quality supply-path spend", 7,
         niche_comp=("ssp_7", 1.1, 0.5)),
]


def _seed_int(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)


def _hours(spec: Spec) -> set[int]:
    if not spec.dayparts:
        return set(range(24))
    out: set[int] = set()
    for part in spec.dayparts:
        a, b = part.split("-")
        out.update(range(int(a), int(b)))
    return out


def _lognormal(rng: random.Random, median: float, sigma: float) -> float:
    return math.exp(rng.gauss(math.log(median), sigma))


def _sample_row(rng, keep, ts, site, seller, geo, device, floor, our_bid,
                winning_price, outcome, samples):
    if rng.random() < keep:
        samples.append({
            "ts": ts, "site_app": site, "seller": seller, "geo": geo,
            "device": device, "floor_price": round(floor, 4),
            "our_bid": round(our_bid, 4),
            "winning_price": round(winning_price, 4), "outcome": outcome,
        })


def simulate(spec: Spec, seed: int) -> dict:
    rng = random.Random(_seed_int(f"{seed}:{spec.campaign_id}"))
    hours_on = _hours(spec)
    start = date.fromisoformat(FLIGHT_START)

    # план пейсинга считается на все 24ч — даже если daypart уже (модель бага FM4)
    hourly_cap = None
    if spec.pacing == "even":
        hourly_cap = spec.budget_total / (FLIGHT_DAYS * 24) * 1.1

    samples: list[dict] = []
    hourly: list[dict] = []
    seller_spend: dict[str, float] = {}
    budget_left = spec.budget_total
    spend_total = 0.0
    wins_total = 0
    bids_total = 0
    active_hours: set[int] = set()
    last_day = 0

    for d in range(FLIGHT_DAYS):
        day_iso = (start + timedelta(days=d)).isoformat()
        for h in sorted(hours_on):
            n_req = max(1, int(rng.gauss(BASE_RPH * spec.base_mult,
                                         BASE_RPH * spec.base_mult * 0.15)))
            hour_spend = 0.0
            h_bids = h_wins = 0
            for _ in range(n_req):
                ts = f"{day_iso}T{h:02d}:{rng.randrange(60):02d}:{rng.randrange(60):02d}Z"
                geo = rng.choice(GEOS)
                device = rng.choice(DEVICES)
                if spec.niche_comp and rng.random() < NICHE_TRAFFIC:
                    seller = spec.niche_comp[0]
                else:
                    seller = rng.choice([s for s in SELLERS
                                         if not spec.niche_comp or s != spec.niche_comp[0]])
                site = rng.choice(SITES)

                if geo not in spec.geo:
                    _sample_row(rng, SAMPLE_KEEP, ts, site, seller, geo, device,
                                FLOOR_MEDIAN, spec.bid, 0.0,
                                "dropped_targeting", samples)
                    continue
                if spec.freq_drop and rng.random() < spec.freq_drop:
                    _sample_row(rng, SAMPLE_KEEP, ts, site, seller, geo, device,
                                FLOOR_MEDIAN, spec.bid, 0.0,
                                "dropped_freq_cap", samples)
                    continue
                if hourly_cap is not None and hour_spend >= hourly_cap:
                    continue  # пейсинг: не бидим — в логи не попадает
                if budget_left <= 0:
                    continue

                if spec.high_floor_share and rng.random() < spec.high_floor_share:
                    floor = _lognormal(rng, HIGH_FLOOR_MEDIAN, FLOOR_SIGMA)
                else:
                    floor = _lognormal(rng, FLOOR_MEDIAN, FLOOR_SIGMA)
                our_bid = max(0.05, spec.bid * (1 + rng.gauss(0, 0.03)))
                if spec.niche_comp and seller == spec.niche_comp[0]:
                    c1 = _lognormal(rng, spec.niche_comp[1], spec.niche_comp[2])
                else:
                    c1 = _lognormal(rng, spec.comp_median, COMP_SIGMA)

                bids_total += 1
                h_bids += 1
                active_hours.add(h)
                if our_bid < floor:
                    _sample_row(rng, SAMPLE_KEEP, ts, site, seller, geo, device,
                                floor, our_bid, max(floor, c1),
                                "loss_below_floor", samples)
                    continue
                if our_bid <= c1:
                    _sample_row(rng, SAMPLE_KEEP, ts, site, seller, geo, device,
                                floor, our_bid, c1, "loss_outbid", samples)
                    continue

                pay = our_bid if spec.auction_model == "first_price" else max(floor, c1)
                pay = round(pay, 4)
                hour_spend += pay
                budget_left -= pay
                spend_total += pay
                wins_total += 1
                h_wins += 1
                seller_spend[seller] = seller_spend.get(seller, 0.0) + pay
                last_day = max(last_day, d + 1)
                _sample_row(rng, SAMPLE_KEEP, ts, site, seller, geo, device,
                            floor, our_bid, pay, "win", samples)

            hourly.append({
                "date": day_iso, "hour": h,
                "impressions": h_wins, "spend": round(hour_spend, 2),
                "bids": h_bids, "wins": h_wins,
            })

    n_samples = len(samples) or 1
    drop_share = sum(1 for s in samples if s["outcome"] == "dropped_freq_cap") / n_samples
    floor_share = sum(1 for s in samples if s["outcome"] == "loss_below_floor") / n_samples
    top_seller = max(seller_spend.values()) if seller_spend else 0.0

    settings = {
        "campaign_id": spec.campaign_id,
        "budget_total": spec.budget_total,
        "flight_start": FLIGHT_START,
        "flight_end": (start + timedelta(days=FLIGHT_DAYS - 1)).isoformat(),
        "pacing": spec.pacing,
        "daily_budget_cap": spec.budget_total / FLIGHT_DAYS if spec.pacing == "even" else None,
        "bid": spec.bid,
        "bid_strategy": "fixed",
        "targeting": {"geo": list(spec.geo), "audience": ["broad"],
                      "inventory": ["open_exchange"]},
        "frequency_cap": {"per_day": spec.freq_cap_per_day},
        "dayparts": list(spec.dayparts) if spec.dayparts else None,
        "auction_model": spec.auction_model,
    }
    stats = {
        "campaign_id": spec.campaign_id, "mode": spec.mode,
        "bids": bids_total, "wins": wins_total,
        "win_rate": round(wins_total / bids_total, 4) if bids_total else 0.0,
        "spend": round(spend_total, 2),
        "delivery_ratio": round(spend_total / spec.budget_total, 4),
        "freq_drop_share": round(drop_share, 4),
        "below_floor_share": round(floor_share, 4),
        "active_hours_per_day": len(active_hours),
        "last_delivery_day": last_day,
        "top_seller_spend_share": round(top_seller / spend_total, 4) if spend_total else 0.0,
    }
    return {"settings": settings, "hourly": hourly, "samples": samples, "stats": stats}


def write_campaign(out_dir: Path, result: dict) -> None:
    cdir = out_dir / result["settings"]["campaign_id"]
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "campaign_settings.json").write_text(
        json.dumps(result["settings"], indent=2) + "\n", encoding="utf-8")

    with (cdir / "delivery_hourly.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "hour", "impressions",
                                          "spend", "bids", "wins"])
        w.writeheader()
        w.writerows(result["hourly"])

    daily: dict[str, dict] = {}
    for r in result["hourly"]:
        d = daily.setdefault(r["date"], {"date": r["date"], "impressions": 0,
                                         "spend": 0.0, "bids": 0, "wins": 0})
        d["impressions"] += r["impressions"]
        d["spend"] = round(d["spend"] + r["spend"], 2)
        d["bids"] += r["bids"]
        d["wins"] += r["wins"]
    with (cdir / "delivery_daily.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "impressions", "spend",
                                          "bids", "wins"])
        w.writeheader()
        w.writerows(sorted(daily.values(), key=lambda x: x["date"]))

    with (cdir / "bid_samples.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "site_app", "seller", "geo", "device",
                                          "floor_price", "our_bid",
                                          "winning_price", "outcome"])
        w.writeheader()
        w.writerows(result["samples"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/datasets")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"generator_version": "0", "seed": args.seed, "campaigns": {}}
    print(f"{'campaign':16} {'mode':4} {'win_rate':>9} {'delivery':>9} "
          f"{'freq%':>6} {'floor%':>7} {'last_day':>8} {'topSeller%':>10}")
    for spec in SPECS:
        result = simulate(spec, args.seed)
        write_campaign(out_dir, result)
        manifest["campaigns"][spec.campaign_id] = {
            "name": spec.name, "mode": spec.mode, "seed_key": f"{args.seed}:{spec.campaign_id}",
        }
        st = result["stats"]
        print(f"{st['campaign_id']:16} {st['mode']:<4} {st['win_rate']:>9} "
              f"{st['delivery_ratio']:>9} {st['freq_drop_share']*100:>6.1f} "
              f"{st['below_floor_share']*100:>7.1f} {st['last_delivery_day']:>8} "
              f"{st['top_seller_spend_share']*100:>10.1f}")
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
