# DEMO — how to present Campaign Doctor (demo/video guide)

Every mode is fully offline: **no keys required**. Keys (Meta API / Baseten / HF) only
switch the live LLM mode — the demo does not depend on them.

## Startup (recommended stack: the real simulator)

Three terminals, from the repo root:

```bash
# T1 — simulator (real, deterministic, offline)
python3 simulator/server.py --port 8100

# T2 — backend (real datasets from /data, heuristic agent mode)
SIMULATOR_BASE_URL=http://127.0.0.1:8100 backend/.venv/bin/uvicorn backend.api.main:app --port 8000

# T3 — frontend
cd ui && npm run dev
```

UI: http://localhost:5173 (or the port vite reports). Swagger: http://localhost:8000/docs.

Readiness check — http://localhost:8000/api/health must show:
`agent_mode: "heuristic"`, `data_source: "data-dir"`, `simulator: "http://127.0.0.1:8100"`.

## Simplified mode (one terminal)

Only T2, WITHOUT `SIMULATOR_BASE_URL` — the simulator is replaced by a deterministic mock.
Everything works (diagnoses, evidence, before/after), **but fm4_daypart and fm5_asap
fixes are not verified** — a mock-model limitation. Use the full stack for the video.

## The 3-minute script (PRD §10)

| Time | Action | What to say |
|---|---|---|
| 0:00–0:20 | Dataset screen → pick `fm1_bid_low` | "This campaign delivers only 22% of its budget. Let's ask the agent why" |
| 0:20–1:20 | Ask: *"Why is this campaign only delivering 22% of budget?"* — watch the live trace | "The agent plans the check itself: aggregates delivery, dissects bid samples, compares against the benchmark. Every step is a tool call with data, not a guess" |
| 1:20–2:10 | Open findings: cause + evidence; press Simulate on the fix | "A diagnosis with proof. And the fix is not just advice: it is replayed in the auction simulator — impressions 2.3k→7.8k, verified. A fix that misses the +5% threshold stays unverified" |
| 2:10–2:35 | Switch to `control_healthy`, ask *"Is anything wrong?"* | "The anti-hallucination test: on a healthy campaign the agent must say 'no problem' — and it does. 0 false positives in the evals" |
| 2:35–3:00 | Open the README (eval table) | "Every target exceeded: top-1 100%, fix success 100%, groundedness 100%. Judges can re-run: `backend/evals/run_evals.py`" |

## Good backup demos

- `fm5_asap` — "the budget burned in 2 days" → even-pacing fix; the notes show delivery spread 3→14 days.
- `fm7_supply` — "82% of budget at a single seller" → block it; concentration drops 0.82→0.22.
- The rerun button with a new seed — determinism/reproducibility.

## Pre-recording checklist

- [ ] `GET /api/health` — green statuses (above)
- [ ] One full dry run of the script
- [ ] Browser window ~1440×900, zoom 110–125% (trace readability)
- [ ] Window layout: UI on the left, the trace not clipped

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: fastapi` | run via `backend/.venv/bin/uvicorn`; the venv is already built |
| Port 8000/8100 busy | `--port 8010` and update `SIMULATOR_BASE_URL` |
| UI can't see the backend | restart `npm run dev` after the backend starts (CORS is already open) |
| "mock" badge in the UI | that's the simulator: start T1 and set `SIMULATOR_BASE_URL` (see above) |
