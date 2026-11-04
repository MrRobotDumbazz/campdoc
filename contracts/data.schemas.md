# Data schemas v1 (seam B1)

**Contract owner:** S-1 (dual-key amendments, I4/I22). **Data generator:** zone B (`/data`). **Consumers:** zone A (tools), zone B (simulator, evals).
Formats: CSV for tables, JSON for nested structures. Input schema validation is the tools' duty (zone A); the generator must produce data that passes validation.

## 1. delivery_daily.csv

| Column | Type | Example |
|---|---|---|
| date | YYYY-MM-DD | 2026-10-20 |
| impressions | int | 41200 |
| spend | float | 318.44 |
| bids | int | 2100000 |
| wins | int | 41200 |

## 2. delivery_hourly.csv

Same columns + `hour` (0–23), `date`.

## 3. campaign_settings.json

```
{
  "campaign_id": "string",
  "budget_total": number,
  "flight_start": "YYYY-MM-DD", "flight_end": "YYYY-MM-DD",
  "pacing": "even|asap",
  "daily_budget_cap": number|null,
  "bid": number, "bid_strategy": "fixed|goal_based",
  "targeting": {"geo": [...], "audience": [...], "inventory": [...]},
  "frequency_cap": {"per_day": int|null},
  "dayparts": ["00-08", "18-23"] | null,
  "auction_model": "first_price|second_price"
}
```

## 4. bid_samples.csv (anonymized)

| Column | Type | Example |
|---|---|---|
| ts | ISO-8601 | 2026-10-20T14:03:11Z |
| site_app | string (pseudonym) | app_412 |
| seller | string (pseudonym) | ssp_7 |
| geo | ISO code | US-NY |
| device | enum | mobile, desktop, ctv |
| floor_price | float | 2.10 |
| our_bid | float | 1.85 |
| winning_price | float | 2.30 |
| outcome | enum | win, loss_below_floor, loss_outbid, dropped_freq_cap, dropped_targeting, dropped_schedule, no_bid_budget |

For dropped_* and no_bid_budget rows: `winning_price` is the estimated winner's price (top competitor); no payment happened; `our_bid` is the bid the campaign would have made. These rows are the simulator's replay material (daypart/pacing/floor changes).
Change v0.1 (S-1, 2026-10-27): added the outcomes `dropped_schedule`, `no_bid_budget`; drop rows previously carried a constant floor and market=0.

## 5. Benchmark: healthy control

A separate campaign `control_healthy` with the same schemas — the reference for compare_to_benchmark.

## Failure modes in the data (the generator must be able to seed all PRD §8 modes, 1–8)

The seed is fixed and recorded in `data/manifest.json` for eval reproducibility.
