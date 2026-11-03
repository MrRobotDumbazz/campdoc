# Campaign Doctor — eval results (PRD §9)

Run configuration: seed 42, datasets: data-dir (/home/mrrobotdumbazz/campdoc/data/datasets), verifier: rule-based, **heuristic-mode (LLM pending), simulator: mock**.

| metric | result | target |
|---|---|---|
| Diagnosis top-1 | 100.0% | ≥ 80% |
| Diagnosis top-3 | 100.0% | ≥ 90% |
| Groundedness (verifier) | 100.0% (8/8) | ≥ 95% |
| Fix success (simulator verified) | 71.4% | ≥ 75% |
| False positives on healthy control | 0 | 0 |
| Median diagnosis time | 11 ms | < 60 s |

Per-campaign detail:

| campaign | mode | top1 | top3 | groundedness | fix verified | time |
|---|---|---|---|---|---|---|
| control_healthy | 0 | ✅ | ✅ | 1/1 | — | 12 ms |
| fm1_bid_low | 1 | ✅ | ✅ | 1/1 | yes | 20 ms |
| fm2_narrow | 2 | ✅ | ✅ | 1/1 | yes | 3 ms |
| fm3_freqcap | 3 | ✅ | ✅ | 1/1 | yes | 11 ms |
| fm4_daypart | 4 | ✅ | ✅ | 1/1 | no | 11 ms |
| fm5_asap | 5 | ✅ | ✅ | 1/1 | no | 12 ms |
| fm6_floor | 6 | ✅ | ✅ | 1/1 | yes | 20 ms |
| fm7_supply | 7 | ✅ | ✅ | 1/1 | yes | 11 ms |
