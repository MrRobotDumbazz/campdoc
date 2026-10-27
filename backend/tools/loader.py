"""Dataset loading + schema validation per /contracts/data.schemas.md.

If the shared data dir (zone B /data) is empty or absent, deterministic
demo datasets are synthesized in-process (clearly labelled MOCK) so that
the frontend (W-2) and evals can run from Day 1 (mock-first, B2).
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .base import ToolError

SCHEMA_DELIVERY_DAILY = ["date", "impressions", "spend", "bids", "wins"]
SCHEMA_DELIVERY_HOURLY = ["date", "hour", "impressions", "spend", "bids", "wins"]
SCHEMA_BID_SAMPLES = [
    "ts", "site_app", "seller", "geo", "device",
    "floor_price", "our_bid", "winning_price", "outcome",
]
OUTCOMES = {"win", "loss_below_floor", "loss_outbid", "dropped_freq_cap", "dropped_targeting"}
DEVICES = {"mobile", "desktop", "ctv"}

FLIGHT_DAYS = 14
FLIGHT_END = date(2026, 10, 24)
SAMPLES_PER_CAMPAIGN = 2000
SCALE = 40  # each sampled request represents ~40 real requests (transparent assumption)
# единый плановый бюджет: 2M показов reference volume по контрольному eCPM (~$2.07)
REFERENCE_BUDGET = round(2_000_000 / 1000 * 2.25 * 0.92, 2)


class DataValidationError(ToolError):
    """Schema violation with a plain-language description (PRD 6.1)."""


@dataclass
class BidSample:
    ts: str
    site_app: str
    seller: str
    geo: str
    device: str
    floor_price: float
    our_bid: float
    winning_price: float
    outcome: str


@dataclass
class CampaignDataset:
    campaign_id: str
    name: str
    healthy: bool
    source: str  # "data-dir" | "mock"
    settings: dict[str, Any]
    daily: list[dict[str, Any]] = field(default_factory=list)
    hourly: list[dict[str, Any]] = field(default_factory=list)
    bid_samples: list[BidSample] = field(default_factory=list)
    ground_truth_mode: int | None = None  # eval use only (PRD §8)


def _float(v: str) -> float:
    return float(v)


def _int(v: str) -> int:
    return int(float(v))


def _validate_columns(path: Path, expected: list[str], header: list[str]) -> None:
    missing = [c for c in expected if c not in header]
    if missing:
        raise DataValidationError(
            f"{path.name}: missing required column(s): {', '.join(missing)}. "
            f"Expected schema: {', '.join(expected)} (contracts/data.schemas.md)."
        )


def _validate_row(path: Path, lineno: int, row: dict[str, str], kind: str) -> None:
    problems: list[str] = []
    try:
        if kind == "daily":
            date.fromisoformat(row["date"])
        else:
            date.fromisoformat(row["date"])
            hour = _int(row["hour"])
            if not 0 <= hour <= 23:
                problems.append(f"hour {hour} not in 0..23")
        for col in ("impressions", "bids", "wins"):
            if _int(row[col]) < 0:
                problems.append(f"{col} negative")
        if _float(row["spend"]) < 0:
            problems.append("spend negative")
    except ValueError as e:
        problems.append(str(e))
    if problems:
        raise DataValidationError(f"{path.name} line {lineno}: {'; '.join(problems)}")


def _load_csv(path: Path, schema: list[str]) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        _validate_columns(path, schema, reader.fieldnames or [])
        kind = "daily" if "hour" not in schema else "hourly"
        rows: list[dict[str, Any]] = []
        for i, row in enumerate(reader, start=2):
            _validate_row(path, i, row, kind)
            out: dict[str, Any] = {
                "date": row["date"],
                "impressions": _int(row["impressions"]),
                "spend": round(_float(row["spend"]), 2),
                "bids": _int(row["bids"]),
                "wins": _int(row["wins"]),
            }
            if kind == "hourly":
                out["hour"] = _int(row["hour"])
            rows.append(out)
    return rows


def _load_bid_samples(path: Path) -> list[BidSample]:
    samples: list[BidSample] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        _validate_columns(path, SCHEMA_BID_SAMPLES, reader.fieldnames or [])
        for i, row in enumerate(reader, start=2):
            problems: list[str] = []
            if row["outcome"] not in OUTCOMES:
                problems.append(f"outcome '{row['outcome']}' not in {sorted(OUTCOMES)}")
            if row["device"] not in DEVICES:
                problems.append(f"device '{row['device']}' not in {sorted(DEVICES)}")
            try:
                datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
                fp, ob, wp = _float(row["floor_price"]), _float(row["our_bid"]), _float(row["winning_price"])
                if min(fp, ob, wp) < 0:
                    problems.append("negative price")
            except ValueError as e:
                problems.append(str(e))
            if problems:
                raise DataValidationError(f"{path.name} line {i}: {'; '.join(problems)}")
            samples.append(BidSample(
                ts=row["ts"], site_app=row["site_app"], seller=row["seller"],
                geo=row["geo"], device=row["device"],
                floor_price=round(fp, 4), our_bid=round(ob, 4), winning_price=round(wp, 4),
                outcome=row["outcome"],
            ))
    return samples


def _validate_settings(campaign_id: str, s: dict[str, Any]) -> None:
    required = ["campaign_id", "budget_total", "flight_start", "flight_end", "pacing",
                "bid", "bid_strategy", "targeting", "frequency_cap", "auction_model"]
    missing = [k for k in required if k not in s]
    if missing:
        raise DataValidationError(
            f"campaign_settings.json [{campaign_id}]: missing key(s): {', '.join(missing)}"
        )
    if s["pacing"] not in ("even", "asap"):
        raise DataValidationError(f"campaign_settings.json [{campaign_id}]: pacing must be even|asap")
    if s["auction_model"] not in ("first_price", "second_price"):
        raise DataValidationError(f"campaign_settings.json [{campaign_id}]: auction_model must be first_price|second_price")


# --------------------------------------------------------------------------- #
# Deterministic demo datasets (MOCK, replaces itself with /data when present)  #
# --------------------------------------------------------------------------- #

MOCK_CAMPAIGNS: list[dict[str, Any]] = [
    {"id": "camp_001_bid_low", "name": "Q4 Retargeting — East", "mode": 1},
    {"id": "camp_002_narrow", "name": "Prospecting — Core Meta", "mode": 2},
    {"id": "camp_003_freq_cap", "name": "Brand Awareness — Reach", "mode": 3},
    {"id": "camp_004_daypart", "name": "Commute Burst — Mobile", "mode": 4},
    {"id": "camp_005_asap", "name": "Launch Blitz — Conversions", "mode": 5},
    {"id": "camp_006_floors", "name": "Premium Display — Q4", "mode": 6},
    {"id": "camp_007_sellers", "name": "Wide Reach Remnant", "mode": 7},
    {"id": "control_healthy", "name": "Control — Healthy Baseline", "mode": 8},
]

_MODE_HINTS = {
    1: {"bid": 1.85, "win_share": 0.30, "outbid": 0.58, "below_floor": 0.04, "delivery_pct": 0.55},
    2: {"bid": 2.60, "win_share": 0.86, "volume_factor": 0.16, "delivery_pct": 0.48},
    3: {"bid": 2.40, "win_share": 0.42, "freq_drop": 0.38, "delivery_pct": 0.60},
    4: {"bid": 2.20, "win_share": 0.55, "concentrated_hours": [20, 21, 22, 23], "delivery_pct": 0.52},
    5: {"bid": 2.30, "win_share": 0.55, "delivery_pct": 1.0},
    6: {"bid": 1.95, "win_share": 0.35, "below_floor": 0.55, "delivery_pct": 0.58},
    7: {"bid": 2.10, "win_share": 0.52, "bad_sellers": ["ssp_13", "ssp_17"], "delivery_pct": 0.70},
    8: {"bid": 2.25, "win_share": 0.52, "delivery_pct": 0.96},
}

_GEOS = ["US-NY", "US-CA", "US-IL", "US-TX", "US-FL", "US-WA"]
_AUDIENCES = ["lookalike_2pct", "interest_tech", "interest_travel", "retarget_30d"]
_INVENTORY = ["app_412", "app_388", "site_109", "site_233", "ctv_51"]


def _mock_settings(rng: random.Random, cid: str, mode: int) -> dict[str, Any]:
    h = _MODE_HINTS[mode]
    geo_n = 4 if mode != 2 else 1
    return {
        "campaign_id": cid,
        "budget_total": REFERENCE_BUDGET,
        "flight_start": (FLIGHT_END - timedelta(days=FLIGHT_DAYS - 1)).isoformat(),
        "flight_end": FLIGHT_END.isoformat(),
        "pacing": "asap" if mode == 5 else "even",
        "daily_budget_cap": round(REFERENCE_BUDGET / FLIGHT_DAYS, 2) if mode in (4, 5) else None,
        "bid": h["bid"],
        "bid_strategy": "fixed",
        "targeting": {
            "geo": rng.sample(_GEOS, geo_n),
            "audience": rng.sample(_AUDIENCES, 1 if mode == 2 else 3),
            "inventory": list(_INVENTORY),
        },
        "frequency_cap": {"per_day": 2 if mode == 3 else 6},
        "dayparts": ["20-23"] if mode == 4 else None,
        "auction_model": "second_price",
    }


def _mock_delivery(rng: random.Random, mode: int, budget: float) -> tuple[list[dict], list[dict]]:
    h = _MODE_HINTS[mode]
    # reference: 2M impressions over the flight at full pace; scale by mode volume+delivery
    base_daily_impr = max(int(2_000_000 * h["delivery_pct"]
                              * h.get("volume_factor", 1.0) / FLIGHT_DAYS), 3000)
    cpm = h["bid"] * (1.15 if mode == 7 else 0.92)
    daily: list[dict] = []
    hourly: list[dict] = []
    spent_total = 0.0
    for d in range(FLIGHT_DAYS):
        day = (FLIGHT_END - timedelta(days=FLIGHT_DAYS - 1 - d)).isoformat()
        if mode == 5:
            # aggressive pacing: 2.5x pace until budget exhausted, then zero
            factor = 2.5 if spent_total < budget * 0.98 else 0.0
        else:
            factor = 1.0 + rng.uniform(-0.08, 0.08)
        impr = int(base_daily_impr * factor)
        spend = impr / 1000 * cpm
        if mode == 5 and spent_total + spend > budget:
            spend = max(budget - spent_total, 0.0)
            impr = int(spend * 1000 / cpm)
        spent_total += spend
        bids = int(impr / max(h["win_share"], 0.05))
        wins = impr
        daily.append({"date": day, "impressions": impr, "spend": round(spend, 2), "bids": bids, "wins": wins})
        # hourly split
        concentrated = h.get("concentrated_hours")
        if concentrated:
            weights = [0.9 if hr in concentrated else 0.15 for hr in range(24)]
        else:
            weights = [0.4 + 0.6 * (1 if 18 <= hr <= 23 else 0.4) for hr in range(24)]
        wsum = sum(weights)
        for hr in range(24):
            h_impr = int(impr * weights[hr] / wsum)
            h_spend = h_impr / 1000 * cpm
            hourly.append({"date": day, "hour": hr, "impressions": h_impr,
                           "spend": round(h_spend, 2), "bids": int(h_impr / max(h["win_share"], 0.05)),
                           "wins": h_impr})
    return daily, hourly


def _mock_bid_samples(rng: random.Random, mode: int, settings: dict) -> list[BidSample]:
    h = _MODE_HINTS[mode]
    bad = set(h.get("bad_sellers", []))
    sellers = ["ssp_" + str(i) for i in (3, 7, 13, 17, 21, 29)]
    sites = ["app_412", "app_388", "site_109", "site_233", "ctv_51"]
    samples: list[BidSample] = []
    start = datetime.fromisoformat(settings["flight_start"] + "T00:00:00+00:00")
    for i in range(SAMPLES_PER_CAMPAIGN):
        ts = (start + timedelta(seconds=rng.randint(0, FLIGHT_DAYS * 86400 - 1))).isoformat().replace("+00:00", "Z")
        seller = rng.choice(sellers)
        site = rng.choice(sites)
        geo = rng.choice(settings["targeting"]["geo"])
        device = rng.choices(["mobile", "desktop", "ctv"], weights=[0.6, 0.3, 0.1])[0]
        our_bid = round(settings["bid"] * rng.uniform(0.96, 1.04), 4)
        if mode == 7 and seller in bad:
            floor = round(rng.uniform(1.15, 1.5), 4)   # cheap remnant supply
        elif mode == 7:
            floor = round(rng.uniform(1.9, 2.6), 4)    # quality supply we lose
        elif mode == 6:
            floor = round(rng.uniform(1.7, 2.6), 4)
        else:
            floor = round(rng.uniform(1.2, 1.9), 4)
        if mode == 1:
            # market above our bid but within reach: bid raise can recover wins
            competitor = round(floor * rng.uniform(1.0, 1.9), 4)
        elif mode == 2:
            competitor = round(rng.uniform(0.8, 1.6), 4)
        elif mode == 7 and seller in bad:
            competitor = round(floor * rng.uniform(0.7, 0.95), 4)  # we win cheap junk
        else:
            competitor = round(floor * rng.uniform(0.85, 1.35), 4)
        r = rng.random()
        if mode == 3 and r < h.get("freq_drop", 0.0):
            outcome, winner_price = "dropped_freq_cap", max(competitor, floor)
        elif mode == 2 and r < 0.05:
            outcome, winner_price = "dropped_targeting", max(competitor, floor)
        elif our_bid < floor:
            outcome, winner_price = "loss_below_floor", max(competitor, floor)
        elif our_bid <= competitor:
            outcome, winner_price = "loss_outbid", competitor
        else:
            outcome = "win"
            winner_price = our_bid if settings["auction_model"] == "first_price" else competitor
        samples.append(BidSample(
            ts=ts, site_app=site, seller=seller, geo=geo, device=device,
            floor_price=floor, our_bid=our_bid,
            winning_price=round(winner_price, 4), outcome=outcome,
        ))
    return samples


def _build_mock_datasets() -> dict[str, CampaignDataset]:
    out: dict[str, CampaignDataset] = {}
    for spec in MOCK_CAMPAIGNS:
        rng = random.Random(f"campdoc-mock::{spec['id']}")
        mode = spec["mode"]
        settings = _mock_settings(rng, spec["id"], mode)
        daily, hourly = _mock_delivery(rng, mode, float(settings["budget_total"]))
        samples = _mock_bid_samples(rng, mode, settings)
        out[spec["id"]] = CampaignDataset(
            campaign_id=spec["id"], name=spec["name"], healthy=(mode == 8),
            source="mock", settings=settings, daily=daily, hourly=hourly,
            bid_samples=samples, ground_truth_mode=mode,
        )
    return out


def _manifest_healthy(manifest: dict, cid: str) -> bool:
    entry = manifest.get("campaigns", {}).get(cid, {})
    mode = entry.get("failure_mode")
    return mode in (0, 8, None, "none", "healthy") and cid.startswith("control")


def _load_data_dir(data_dir: Path) -> dict[str, CampaignDataset]:
    manifest: dict = {}
    manifest_path = data_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise DataValidationError(f"manifest.json: invalid JSON ({e})")
    datasets: dict[str, CampaignDataset] = {}
    for camp_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        cid = camp_dir.name
        settings_path = camp_dir / "campaign_settings.json"
        if not settings_path.exists():
            raise DataValidationError(f"{camp_dir.name}/: campaign_settings.json not found")
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise DataValidationError(f"{cid}/campaign_settings.json: invalid JSON ({e})")
        _validate_settings(cid, settings)
        daily_p = camp_dir / "delivery_daily.csv"
        hourly_p = camp_dir / "delivery_hourly.csv"
        bids_p = camp_dir / "bid_samples.csv"
        for p in (daily_p, hourly_p, bids_p):
            if not p.exists():
                raise DataValidationError(f"{cid}/: required file {p.name} not found (contracts/data.schemas.md)")
        datasets[cid] = CampaignDataset(
            campaign_id=cid, name=str(manifest.get("campaigns", {}).get(cid, {}).get("name", cid)),
            healthy=_manifest_healthy(manifest, cid),
            source="data-dir", settings=settings,
            daily=_load_csv(daily_p, SCHEMA_DELIVERY_DAILY),
            hourly=_load_csv(hourly_p, SCHEMA_DELIVERY_HOURLY),
            bid_samples=_load_bid_samples(bids_p),
            ground_truth_mode=manifest.get("campaigns", {}).get(cid, {}).get("failure_mode"),
        )
    return datasets


class DatasetRepository:
    """Loads datasets once; falls back to deterministic mocks when /data is empty."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._datasets: dict[str, CampaignDataset] | None = None

    def _load(self) -> dict[str, CampaignDataset]:
        if self._datasets is not None:
            return self._datasets
        if self._data_dir.is_dir() and any(p.is_dir() for p in self._data_dir.iterdir()):
            self._datasets = _load_data_dir(self._data_dir)
        else:
            self._datasets = _build_mock_datasets()
        return self._datasets

    def list_campaigns(self) -> list[dict[str, Any]]:
        return [
            {"campaign_id": d.campaign_id, "name": d.name, "healthy": d.healthy}
            for d in sorted(self._load().values(), key=lambda x: x.campaign_id)
        ]

    def using_mock_data(self) -> bool:
        ds = next(iter(self._load().values()))
        return ds.source == "mock"

    def get(self, campaign_id: str) -> CampaignDataset:
        ds = self._load().get(campaign_id)
        if ds is None:
            known = ", ".join(sorted(self._load())) or "none"
            raise ToolError(f"Unknown campaign_id '{campaign_id}'. Known campaigns: {known}.")
        return ds

    def stats(self, samples: list[BidSample]) -> dict[str, Any]:
        """Shared aggregate used by tools and the mock simulator."""
        n = len(samples)
        by_outcome: dict[str, int] = {}
        win_prices: list[float] = []
        our_bids: list[float] = []
        for s in samples:
            by_outcome[s.outcome] = by_outcome.get(s.outcome, 0) + 1
            if s.outcome != "win":
                win_prices.append(s.winning_price)
            our_bids.append(s.our_bid)
        return {
            "n": n,
            "by_outcome": by_outcome,
            "competitor_price_median": round(statistics.median(win_prices), 4) if win_prices else None,
            "our_bid_median": round(statistics.median(our_bids), 4) if our_bids else None,
        }
