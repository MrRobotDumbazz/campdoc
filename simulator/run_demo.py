#!/usr/bin/env python3
"""Демо-прогон: известный фикс для каждого failure mode — before/after/verified."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simulate import run_simulation  # noqa: E402

FIXES = {
    "fm1_bid_low": {"changes": {"bid": 2.60}},
    "fm2_narrow": {"changes": {"geo_widen": ["US-NY", "US-CA", "US-TX", "US-FL", "US-IL"]}},
    "fm3_freqcap": {"changes": {"frequency_cap": 5}},
    "fm4_daypart": {"changes": {"dayparts": None}},
    "fm5_asap": {"changes": {"pacing": "even",
                             "daily_budget_cap": 20000 / 14}},
    "fm6_floor": {"changes": {"bid": 7.00}, "target_metric": "spend"},
    "fm7_supply": {"changes": {"block_sellers": ["ssp_7"]}},
    "control_healthy": {"changes": {"bid": 3.0}},
}


def main() -> None:
    print(f"{'campaign':16} {'impr before->after':>22} {'spend b->a':>20} "
          f"{'wr b->a':>14} {'verified':>8}")
    for cid, cfg in FIXES.items():
        out = run_simulation({"campaign_id": cid, "seed": 42,
                              "changes": cfg["changes"],
                              "target_metric": cfg.get("target_metric", "impressions")})
        b, a = out["before"], out["after"]
        print(f"{cid:16} {b['impressions']:>9}->{a['impressions']:<12} "
              f"{b['spend']:>8}->{a['spend']:<11} "
              f"{b['win_rate']:>5.3f}->{a['win_rate']:<8.3f} "
              f"{str(out['verified']):>8}")
        if out["violated_constraints"]:
            print(f"{'':16} violated: {out['violated_constraints']}")


if __name__ == "__main__":
    main()
