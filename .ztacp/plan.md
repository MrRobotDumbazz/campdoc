# Work plan (D1 — Plan-as-Ledger)

**Project:** Campaign Doctor (campdoc). **Event:** Meta Global AI Developer Hackathon, building period Oct 27 – Nov 4.
**Rule:** a step = a commit; a checkbox closes only against a machine-checkable artifact (test/file/SHA, E11). The plan is a shared file, writer S-1. **Status at close: submitted (main).**

## Track 0 — Governance (S-1)
- [x] Genesis: constitution, zones W-1/W-2/W-3, seam contracts v1, lease, registries, research case, CI zone-guard (6bb80b9, 2026-10-27)
- [x] First commit + push; public history from Oct 27 (I48/I52; push later delegated to S-1 via SSH — 1020c6f)
- [ ] CI zone-guard activation on GitHub PRs + acceptance run (branch protection never enabled — L1 walls: C5 staging + human/delegated push; defunct at close)
- [ ] (opt.) L2: CODEOWNERS + machine identities — not reached, honest

## Track A — Backend (W-1 → S-1+subagents at finish, zones /backend /docs)
- [x] D1: FastAPI skeleton per /contracts/app.api.yaml + mock mode; README v0; Muse Spark tool-calling check with fallback (e74b0d9)
- [x] D2: data tools with schema validation (e74b0d9, tests ac98604)
- [x] D2–D3: agent loop, findings JSON with the evidence rule in code, trace persistence (ac98604: 35 tests; S-1 re-run green)
- [x] D4–D5: run_simulation integration — contract tests (ad3d8d4) → real simulator over HTTP at finish (c6f1718)
- [x] D5: verifier pass — rule-based + semantic LLM layer, unsupported claims removed (9c47348: 44 tests)
- [x] D7: eval harness + metrics (6b8447a, 6f5251b, c6f1718) — final run on the real simulator: top-1 100%, top-3 100%, groundedness 100%, fix success 100%, FP 0, median 12 ms (agent=heuristic, LLM pending)
- [x] Finish: loader/schema v0.1 catch-up, target_metric+direction, Baseten/HF/Meta presets (aab1645, fb1cec7, 3b0d3fc, b8d9049, c1822b2, 38d8d72, 18a516c)

## Track F — Frontend (W-2, zone /ui)
- [x] D1: skeleton from app.api.yaml mocks (f01db99; build verified by S-1)
- [x] D2–D3: live trace panel (45781ae)
- [x] D4: before/after panel with verified badges (020970c)
- [x] D5–D6: report download, loading states, live/mock badge (900cd2b)
- [x] Finish: full English UI strings + locales (ccd94ec)

## Track B — ML (S-1 acting — contingency #1 from 2026-10-27; zones /simulator /data)
- [x] D1: synthetic data generator v0 per data.schemas.md (13f910a)
- [x] D2–D3: full generator — 8 campaigns, all PRD §8 modes, manifest with seeds; 10 tests (13f910a, 8c25ff9)
- [x] D3: simulator v0 — deterministic replay, first/second price, pacing layers; calibration vs ground truth ±5% (900265a, a379ac2)
- [x] D5: contract v1-draft.1 conformance (target_direction, pacing block) + HTTP endpoint + tests (a379ac2, 1d314e5)

## Track T — Human-only (P-1, P-2)
- [x] D1: credit applications — Meta $150 (both, individually), Baseten/Modal — submitted Day 1 (granted: none — see README "model access")
- [ ] Video 3 min per docs/DEMO.md — P-1 (pending at this commit)
- [x] T-final (P-1's amendment, Nov 3): submit **main as-is** — no sterile branch (risk of perceived history manipulation; transparency wins); CV-platform submission by Nov 4, 9:00 PM ET (aim noon)

## Contingencies (P-1's decisions)
- #1: P-2/W-3 unavailable → ML zone to S-1 (I22). **Activated 2026-10-27, held until close.**
- #2: W-1/W-2 unavailable → P-1 assigns (unused).
- #3: No sterile branch; main as-is (Nov 3).
- Coordinator succession: opencode → codex (unused; lease held by S-1 throughout).

## Milestones (PRD §12 vs actual)
D1 skeletons + generator ✓ · D2–3 tools+loop / simulator ✓ · D4–5 integration + verifier ✓ (recovered Nov 3 after the Oct 28–Nov 2 stall) · D6 UI ✓ · D7 evals ✓ · D8 freeze ✓ · D9 submission — P-1.
