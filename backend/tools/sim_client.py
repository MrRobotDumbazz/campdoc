"""Simulation client per /contracts/simulation.api.yaml.

Two implementations behind one interface (seam B2):
- MockSimulationClient: deterministic in-process model, used until the real
  simulator from zone B (/simulator) is wired via SIMULATOR_BASE_URL (Day 4-5).
- HttpSimulationClient: thin contract client for the real simulator.

The mock replays the campaign's bid-sample cohort under modified settings:
a sampled request wins iff the new bid clears the floor and beats the logged
competitor price. Targeting/frequency-cap widening recovers previously
dropped requests; seller blocks exclude their traffic. No RNG is used, so
identical (input, seed) always yields identical output.
"""
from __future__ import annotations

from typing import Any, Protocol

from .base import ToolError
from .loader import SCALE, CampaignDataset, DatasetRepository

METRIC_KEYS = ("impressions", "spend", "win_rate", "ecpm")
LIMITATION_NOTE = "Симуляция на выборке bid-запросов; прогноз, не гарантия (mock-модель до интеграции с симулятором зоны B)."
DEFAULT_THRESHOLD_PCT = 5.0
# metrics where "improvement" means decrease rather than increase
_LOWER_IS_BETTER = {"spend", "ecpm"}


class SimulationClient(Protocol):
    def run_simulation(self, campaign_id: str, seed: int, changes: dict[str, Any],
                       constraints: dict[str, Any] | None,
                       target_metric: str = "impressions") -> dict[str, Any]: ...


def _effective_bid(settings: dict[str, Any], changes: dict[str, Any]) -> float | None:
    if changes.get("bid") is not None:
        return float(changes["bid"])
    if changes.get("bid_delta_pct") is not None:
        return round(float(settings["bid"]) * (1 + float(changes["bid_delta_pct"]) / 100), 4)
    return None


def _replay(ds: CampaignDataset, changes: dict[str, Any]) -> dict[str, float]:
    settings = ds.settings
    new_bid = _effective_bid(settings, changes)
    bid = new_bid if new_bid is not None else float(settings["bid"])
    auction = settings.get("auction_model", "second_price")
    freq_cap = changes.get("frequency_cap", None)
    widen_geo = set(changes.get("geo_widen") or [])
    widen_aud = set(changes.get("audience_widen") or [])
    dayparts = changes.get("dayparts", None)
    block = set(changes.get("block_sellers") or [])
    pacing = changes.get("pacing", None)
    daily_cap = changes.get("daily_budget_cap", None)

    # hour windows from "HH-HH" strings
    allowed_hours: set[int] | None = None
    if dayparts is not None:
        allowed_hours = set()
        for w in dayparts:
            try:
                a, b = w.split("-")
                allowed_hours |= set(range(int(a), int(b) + 1))
            except ValueError:
                raise ToolError(f"Invalid daypart window '{w}' (expected 'HH-HH').")

    wins = 0
    paid = 0.0
    eligible = 0
    for s in ds.bid_samples:
        if s.seller in block:
            continue
        hour = int(s.ts[11:13])
        if allowed_hours is not None and hour not in allowed_hours:
            continue
        dropped = False
        if s.outcome == "dropped_freq_cap":
            # recovered only if the proposed cap is materially higher than current
            current = settings.get("frequency_cap", {}).get("per_day") or 0
            dropped = freq_cap is None or freq_cap <= current
        elif s.outcome == "dropped_targeting":
            dropped = not (widen_geo or widen_aud)
        eligible += 1
        if dropped:
            continue
        if bid >= s.floor_price and bid > s.winning_price:
            wins += 1
            paid += bid if auction == "first_price" else max(s.winning_price, s.floor_price)

    impressions = wins * SCALE
    spend = paid * SCALE / 1000.0
    win_rate = wins / max(eligible, 1)
    ecpm = spend / max(impressions / 1000.0, 1e-9) if impressions else 0.0

    # pacing / daily cap shape the spend profile without changing auction outcomes;
    # a daily cap can only trim late-flight overspend.
    if daily_cap is not None and pacing == "even":
        flight_days = max(len({r["date"] for r in ds.daily}), 1)
        max_spend = float(daily_cap) * flight_days
        if spend > max_spend:
            spend = max_spend
            impressions = int(impressions * max_spend / max(spend, 1e-9)) if spend else 0

    return {"impressions": impressions, "spend": round(spend, 2),
            "win_rate": round(win_rate, 4), "ecpm": round(ecpm, 4)}


class MockSimulationClient:
    name = "mock"

    def __init__(self, repo: DatasetRepository, threshold_pct: float = DEFAULT_THRESHOLD_PCT):
        self.repo = repo
        self.threshold_pct = threshold_pct

    def run_simulation(self, campaign_id: str, seed: int, changes: dict[str, Any],
                       constraints: dict[str, Any] | None,
                       target_metric: str = "impressions") -> dict[str, Any]:
        if target_metric not in METRIC_KEYS:
            raise ToolError(f"target_metric must be one of {METRIC_KEYS}, got '{target_metric}'.")
        changes = changes or {}
        ds = self.repo.get(campaign_id)
        before = _replay(ds, {})
        after = _replay(ds, changes)
        delta = {k: (round(after[k] - before[k], 4) if isinstance(after[k], float) else after[k] - before[k])
                 for k in METRIC_KEYS}
        delta_pct = {}
        for k in METRIC_KEYS:
            delta_pct[k] = round((after[k] - before[k]) / before[k] * 100, 2) if before[k] else (0.0 if after[k] == before[k] else float("inf"))
        threshold = self.threshold_pct
        if target_metric in _LOWER_IS_BETTER:
            improved = delta_pct[target_metric] <= -threshold
        else:
            improved = delta_pct[target_metric] >= threshold
        violated: list[str] = []
        constraints = constraints or {}
        if constraints.get("budget_cap_total") is not None and after["spend"] > float(constraints["budget_cap_total"]):
            violated.append(f"budget_cap_total: after spend {after['spend']} > cap {constraints['budget_cap_total']}")
        if constraints.get("max_ecpm") is not None and after["ecpm"] > float(constraints["max_ecpm"]):
            violated.append(f"max_ecpm: after ecpm {after['ecpm']} > cap {constraints['max_ecpm']}")
        verified = improved and not violated
        notes = [
            LIMITATION_NOTE,
            f"mock-модель: реплей {len(ds.bid_samples)} сэмплов (SCALE={SCALE}); seed={seed} записан, выход детерминирован",
            "конкурентские цены оценены по залогированным winning_price",
        ]
        return {
            "before": before, "after": after, "delta": delta,
            "delta_pct": delta_pct,
            "verified": verified, "threshold_pct": threshold,
            "violated_constraints": violated, "notes": notes,
        }


class HttpSimulationClient:
    """Contract client for the real simulator (zone B). Active Day 4-5."""

    name = "http"

    def __init__(self, base_url: str, timeout_s: float = 30.0):
        import httpx  # local import: only needed when the real seam is enabled
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s)
        self.base_url = base_url

    def run_simulation(self, campaign_id: str, seed: int, changes: dict[str, Any],
                       constraints: dict[str, Any] | None,
                       target_metric: str = "impressions") -> dict[str, Any]:
        payload = {"campaign_id": campaign_id, "seed": seed, "changes": changes,
                   "constraints": constraints or {}, "target_metric": target_metric}
        resp = self._client.post("/simulate", json=payload)
        if resp.status_code >= 400:
            raise ToolError(f"Simulator error (HTTP {resp.status_code}): {resp.text[:300]}")
        out = resp.json()
        for k in ("before", "after", "delta", "verified", "threshold_pct",
                  "violated_constraints", "notes"):
            if k not in out:
                raise ToolError(f"Simulator response violates contract: missing '{k}' (simulation.api.yaml).")
        return out


def make_simulation_client(repo: DatasetRepository, settings) -> SimulationClient:
    if settings.simulator_base_url:
        return HttpSimulationClient(settings.simulator_base_url, settings.request_timeout_s)
    return MockSimulationClient(repo, settings.simulation_threshold_pct)
