# Campaign Doctor

**A verifiable AI agent that diagnoses and fixes underperforming ad campaigns.**
Built for the Meta Global AI Developer Hackathon 2026, *Build for Your World* track.

Campaign Doctor ingests a campaign's delivery logs, pacing data and a sample of bid
requests, finds the root cause of under-delivery or overspending — every claim backed by
evidence from the data — proposes concrete fixes, and **proves each fix by replaying it
in an auction simulator** (before/after: delivery, spend, win rate, eCPM) before
recommending it. Most hackathon agents stop at "here is a plausible answer"; this one
has to survive its own verification loop.

## What we built (build log)

- **Day 1 (Oct 27):** backend skeleton — FastAPI implementing `/contracts/app.api.yaml`
  (5 endpoints), data tools with schema validation (`/contracts/data.schemas.md`),
  mock simulator (deterministic, per `/contracts/simulation.api.yaml`), agent loop
  (Muse Spark tool-calling with fallback: structured JSON prompting → deterministic
  heuristics), an evidence rule enforced in code ("no tool result — no diagnosis"),
  8 synthetic campaigns (failure modes 1–7 + a healthy control, PRD §8).
- **D2–D3:** machine-verified agent loop (stub server: tool-calling / JSON fallback /
  API refusal), unit tests for the data tools, reports with simulation results
  (before/after, verified badges, plain-English summary), contract tests for the
  simulator HTTP client; live trace panel and before/after panel in the UI.
- **D5:** two-layer verifier — rule-based reference check plus a semantic LLM pass
  (when the API is unavailable, the rule-based verdict stands).
- **Finish day (Nov 3):** real simulator behind the HTTP contract (integration through
  the seam, not imports), contract `v1-draft.1` (target direction + pacing diagnostics),
  eval harness run against the real simulator, Muse Spark Open (Baseten) preset.
- Synthetic datasets live in `/data` (seeds fixed in `data/datasets/manifest.json`);
  current status is always visible at `GET /api/health`.

## Architecture

```
ui (W-2)  ──app.api.yaml──▶  backend (W-1)  ──simulation.api.yaml──▶  simulator (W-3)
                                  │
                                  ├── agent/   agent loop, verifier, heuristics
                                  ├── tools/   query_delivery, query_bid_samples,
                                  │            get_campaign_settings, compare_to_benchmark,
                                  │            run_simulation (mock → real via contract)
                                  ├── api/     FastAPI, store, trace
                                  └── evals/   eval harness (PRD §9)
```

## Quick start

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r requirements.txt
backend/.venv/bin/uvicorn backend.api.main:app --reload --port 8000   # from the repo root
```

- Swagger UI: http://localhost:8000/docs
- Without env keys the agent runs in the deterministic heuristic mode (offline demo).
- Real simulator (finish-day integration):

```bash
python3 simulator/server.py --port 8100          # from the repo root
export SIMULATOR_BASE_URL=http://127.0.0.1:8100  # otherwise the mock client is used
```

- Muse Spark via Meta Model API — **a single variable** (defaults verified against
  dev.meta.ai/docs: OpenAI-compatible, Chat Completions supported):

```bash
export MODEL_API_KEY=...         # base URL and model resolve automatically:
                                 # https://api.meta.ai/v1, muse-spark-1.3
# explicit overrides: MUSE_SPARK_BASE_URL / MUSE_SPARK_MODEL / MUSE_SPARK_API_KEY
backend/.venv/bin/python backend/scripts/check_tool_calling.py   # tool-calling check
```

- Muse Spark Open (open weights) — **a single variable**, two routes:

```bash
export BASETEN_API_KEY=...   # direct: meta-models/muse-spark-open-1026 @ inference.baseten.co/v1
                             # (verify the current URL against docs.baseten.co)
# or, via Hugging Face Inference Providers (verified live: the model is served
# through HF's Baseten provider; HF's OpenAI-compatible router):
export HF_TOKEN=...          # meta-models/Muse-Spark-Open-816B-A42B @ router.huggingface.co/v1
```

- ML-zone datasets: place campaigns under `/data` (schemas in
  `contracts/data.schemas.md`); while the directory is empty, built-in mocks are used.

## A note on model access

We applied for the $150 Meta Model API credits through the official form on Day 1 of
the building period (Oct 27), well before the Nov 4 deadline. Credits are granted in
batches; our request was not fulfilled before our submission freeze, and partner
open-weight inference credits (Baseten) were not granted either. The live demo and
evals therefore run on the documented fallback chain — a deterministic offline
heuristic engine — while the full LLM layer (tool-calling, structured JSON prompting,
LLM verifier) is implemented and unit-tested against stub servers. The agent is
model-agnostic by design (OpenAI-compatible chat completions + tool calling): Muse
Spark via Meta Model API and the open-weight Muse Spark Open
(`meta-models/muse-spark-open-1026`) attach through environment variables with no code
changes (PRD 6.7). The active mode is reported by `GET /api/health` (`agent_mode`).

## Eval results (PRD §9; seed 42; judges can re-run: `backend/.venv/bin/python backend/evals/run_evals.py`)

Run configuration: sim=real (HTTP, contract `simulation.api.yaml` v1-draft.1),
agent=heuristic (deterministic offline engine; the LLM layer attaches via env — see the
model access note). Per-campaign table: `backend/evals/results.md`. Tests: 99 passed.

| Metric | Target | Result |
|---|---|---|
| Diagnosis top-1 | ≥ 80% | **100%** |
| Diagnosis top-3 | ≥ 90% | **100%** |
| Groundedness after verifier | ≥ 95% | **100%** |
| Fix success rate (verified in simulator) | ≥ 75% | **100%** (7/7 modes) |
| False positives on healthy control | 0 | **0** |
| Median diagnosis time | < 60 s | **12 ms** (heuristics, offline) |

## Repository

`/backend` — FastAPI + agent (zone W-1) · `/ui` — frontend (W-2) · `/simulator`, `/data`
— ML (W-3) · `/contracts` — seam contracts · `/docs` — PRD and documentation.
The repo was built by parallel AI-agent sessions under a zero-trust governance layer
(see `AGENTS.md`, `.ztacp/`) with a single human principal — hence the zone-prefixed
commit history. All product code was written during the hackathon (Oct 27 – Nov 4, 2026).

---
*Built during the Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026).
Simulations are a forecast on sampled data, not a guarantee.*
