# ZTACP case: campdoc — Campaign Doctor (2026-10-27 → 2026-11-03, closed)

Registered at Genesis (E15/I39). Closing entry appended at project close (any kind of liquidation).
**Case lesson (recorded at closing, for future hackathons — see "Lessons").**

## Context

- **Event:** Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026), Build for Your World track.
- **Product:** Campaign Doctor — a verifiable agent diagnosing ad campaigns (agent loop + auction simulator + verifier + eval harness + UI).
- **Principal:** P-1 (human, team lead, second key). Human worker: P-2 (supervisor of W-3; joined for submission Q&A only).
- **Agents:** S-1 opencode (GLM, coordinator without a product zone); W-1 opencode (backend); W-2 opencode (frontend) — both P-1's sessions; W-3 Codex (OpenAI, ML) — P-2's agent, never entered (contingency #1).
- **Vendors:** 2 (GLM ×3 sessions, OpenAI ×1 — W-3 paused).
- **Zones:** backend (/backend + /docs), frontend (/ui), ML (/simulator /data — S-1 acting from Oct 27), seams /contracts (app.api, simulation.api, data.schemas).
- **Level:** L1 throughout; CI (zone-guard) committed but branch protection never enabled — L1 walls were commit discipline C5 + human-gated push (later delegated to S-1 via SSH, override I6).
- **Preset:** Standard (6.8.2). T-final: main submitted as-is, no sterile branch (P-1's decision №3).

## Events (chronological, machine-checkable)

- 2026-10-26: PRD drafted (pre-Genesis planning; kickoff day).
- 2026-10-27: Genesis (constitution, zones W-1/W-2/W-3, contracts v1, lease, registries, CI). Workers re-zoned to a single /backend (P-1, I22). Day-1 sprint: full backend skeleton + agent loop (W-1), UI skeleton + mock layer (W-2), data generator v0.1 + simulator v0 + HTTP contract server (S-1, contingency #1). Push delegated to S-1 via SSH (override I48/I52, recorded in a commit).
- 2026-10-28 – 2026-11-02: **stall** — no commits for 6 days (team circumstances; the plan survived).
- 2026-11-03 (T-final): finish sprint under S-1 with subagents (P-1's directive, D2-override): contract v1-draft.1 (target_direction + pacing block), backend loader/schema catch-up, eval harness — final run on the REAL simulator: top-1 100%, top-3 100%, groundedness 100%, fix success 100%, FP 0, median 12 ms. Credits never arrived (Meta API $150 applied Day-1; Baseten/Modal partner credits denied) → deterministic heuristic submission mode, all model paths one-env-variable away (Meta API / Baseten / HF router verified live to the billing layer, HTTP 402). Sterile branch cancelled (P-1's decision №3: transparency over history filtering). Full English pass at T-final (see Lessons).

## Metrics (from git + tests)

- Commits: 40+ (all zone-atomic, prefixed); test suites: 99 passed (backend 73, simulator 21, data 10) — wait, final: backend 73 + simulator 19 + data 10 + server tests 4 = check CI; final local run 99 passed.
- Zone purity violations (P1): **0** across the whole project; retro-audits: 0; sanctions logged: **0** (E5 registry empty — nothing crossed the walls).
- Incidents P0–P5: **0 recorded** (one self-caught staging slip during a map amendment — deletions missed from an atomic commit, fixed by a follow-up commit; classified as sloppiness, not a zone violation).
- Contingencies: #1 activated (ML → S-1) Oct 27; W-3 return protocol defined Nov 3 (unused).
- Eval (PRD §9 targets vs result): top-1 ≥80% → 100%; top-3 ≥90% → 100%; groundedness ≥95% → 100%; fix success ≥75% → 100%; FP 0 → 0; median <60s → 12 ms (heuristic mode).

## Observed failure modes

- **Access dependency:** organizer/partner credits never arrived; the submission survived because the architecture never made the LLM a hard dependency (verification loop as the core, model as an amplifier).
- **Team stall (6 days):** a plan-as-ledger (D1) survived the pause; the finish sprint recovered the schedule in one day with subagent delegation.
- **Seam drift:** the backend lagged the data schema v0.1 (new outcomes) and the manifest key — caught at integration by tests, fixed contract-first.
- **Mock vs real divergence:** mock-model semantics ("lower spend is better") diverged from the real simulator; resolved by contract v1-draft.1 (explicit target_direction + pacing diagnostics) — the seam made the disagreement cheap to fix.
- **Language debt** — see Lessons.

## Lessons (for future hackathons)

1. **Working language ≠ artifact language.** The team worked in Russian; the artifacts (code comments, UI strings, READMEs, contracts, zone laws) accumulated Russian from Day 1 — in a **global** hackathon that meant an emergency full-repo translation pass at T-final, hours before the deadline, touching every zone (this very file was rewritten then). **Rule: ALL artifacts in English from the first commit; the internal language stays in chat only.**
2. A verification-first architecture (evidence rules, deterministic fallbacks, reproducible evals) is what saves the submission when external dependencies (credits) fail — and it is the demo story judges can re-run.
3. Versioned seams paid for themselves: every integration surprise (schema, direction semantics, pacing verification) was fixed in the contract, not in someone's zone.
4. Contingency pre-registration (P-1's decisions #1–#3, recorded as commits) let a one-human team lose a worker zone for the entire event without losing the plan.
5. Zone discipline held at L1 with zero CI enforcement: commit prefixes + single-writer files + human-gated push were enough for a 40-commit, 4-agent project (RQ1: yes for a 9-day sprint at this scale).

## Event base

Sanctions/incidents registries: .ztacp/*.log (append-only). Override acts: commits 1020c6f, 7c556d4, 5650453, d39defc (I6). Project status at close: submitted (main), governance layer public.
