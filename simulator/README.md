# simulator — Campaign Doctor auction simulator

Owner: W-3 (currently S-1 acting, contingency #1). Contract: `/contracts/simulation.api.yaml`.

## Run

```bash
python3 simulator/run_demo.py                                # fix table for every mode
python3 simulator/server.py --port 8100                      # HTTP contract endpoint
backend/.venv/bin/python -m pytest simulator/tests -q        # tests
```

API: `from simulator.simulate import run_simulation` (backend consumes it over the HTTP contract).

## Method (v0)

Deterministic replay of `bid_samples.csv` under modified settings:

1. Filters: block_sellers → dayparts → targeting/geo_widen → freq-cap recovery.
2. Pacing: even = hourly budget allowances across the flight; asap = global budget; daily cap.
3. Auction: `bid < floor` → loss_below_floor; `bid <= winning_price` → loss_outbid;
   otherwise a win, pay = bid (first price) or max(floor, market) (second price).
4. Metrics are scaled from the sample to campaign level (factor = actual bids / bids in sample).

## Assumptions (honest)

- `audience_widen` is not modelled (no audience dimension in the data) — flagged in notes.
- Freq-recovery: drop(C) = 0.93·C_old/C, C=None → 0.
- `verified` in v0 = target_metric moves ≥ threshold in `target_direction` without violating constraints;
  pacing fixes (fm5) show their effect in the `pacing` block (active days/hours), not in Δimpressions.
- Calibration: an unchanged replay reproduces actual delivery aggregates within ±15% (tests;
  in practice ~±5%).
