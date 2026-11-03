# Campaign Doctor — eval results (PRD §9)

Run configuration: seed 42, datasets: data-dir (/home/mrrobotdumbazz/campdoc/data/datasets), verifier: rule-based, **sim=real (HTTP @ http://127.0.0.1:8100, contract simulation.api.yaml v1-draft.1), agent=heuristic (LLM pending open-weights)**.

| metric | result | target |
|---|---|---|
| Diagnosis top-1 | 100.0% | ≥ 80% |
| Diagnosis top-3 | 100.0% | ≥ 90% |
| Groundedness (verifier) | 100.0% (8/8) | ≥ 95% |
| Fix success (simulator verified) | 100.0% | ≥ 75% |
| False positives on healthy control | 0 | 0 |
| Median diagnosis time | 12 ms | < 60 s |

Per-campaign detail:

| campaign | mode | top1 | top3 | groundedness | fix verified | time |
|---|---|---|---|---|---|---|
| control_healthy | 0 | ✅ | ✅ | 1/1 | — | 12 ms |
| fm1_bid_low | 1 | ✅ | ✅ | 1/1 | yes (totals) | 21 ms |
| fm2_narrow | 2 | ✅ | ✅ | 1/1 | yes (totals) | 3 ms |
| fm3_freqcap | 3 | ✅ | ✅ | 1/1 | yes (totals) | 11 ms |
| fm4_daypart | 4 | ✅ | ✅ | 1/1 | yes (totals) | 11 ms |
| fm5_asap | 5 | ✅ | ✅ | 1/1 | yes (totals) | 12 ms |
| fm6_floor | 6 | ✅ | ✅ | 1/1 | yes (totals) | 21 ms |
| fm7_supply | 7 | ✅ | ✅ | 1/1 | yes (totals) | 11 ms |
