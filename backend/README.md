# Backend (zone W-1)

FastAPI server per `/contracts/app.api.yaml`, diagnostic agent with tool calling
(Muse Spark), data tools with `/contracts/data.schemas.md` validation,
groundedness verifier, eval harness (D7).

## Run

```bash
# from the repo root
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r requirements.txt
backend/.venv/bin/python -m pytest                          # tests
backend/.venv/bin/uvicorn backend.api.main:app --reload     # server :8000
```

## Structure

```
backend/
  api/      FastAPI: endpoints, pydantic schemas, investigation store (JSONL trace)
  agent/    runner (LLM/heuristics), llm client, PRD §8 heuristics,
            findings + evidence rule, .md report
  tools/    loader (schema validation + mock datasets), data_tools, sim_client (mock/HTTP)
  evals/    eval harness (D7)
  scripts/  check_tool_calling.py — Day-1 tool-calling format check
  tests/    API contract tests, LLM mode (stub server: tool-calling/json-fallback/
            refusal → heuristics), data tools, evidence rule, schemas, trace persistence
```

## Modes

| What | Enabled by | Behavior |
|---|---|---|
| Agent | `MUSE_SPARK_BASE_URL` + `MUSE_SPARK_API_KEY` | tool-calling → JSON-fallback → heuristics |
| Simulator | `SIMULATOR_BASE_URL` | HTTP client per simulation.api.yaml; otherwise deterministic mock |
| Data | `/data` non-empty | loading + schema validation; otherwise built-in mock campaigns (modes 1–8) |

## Invariants (verified by tests)

- Every finding carries evidence with a ref to an actually executed tool call
  (`backend/agent/findings.py:enforce_evidence`) — "no evidence, no diagnosis" enforced in code.
- Two-layer verifier (`backend/agent/verifier.py`): rule-based ref-check always;
  when Muse Spark is available — semantic check of claims ↔ tool outputs (an API failure
  does not drop justified claims). Groundedness = claims_grounded/claims_total.
- Simulation is deterministic: identical input+seed → identical output;
  "verified" = Δ(target) ≥ 5% without violating constraints.
- Healthy control yields no false diagnoses (FP=0).
- Data schema errors — in plain language with the column/row name.

## Contract notes

- `GET /api/health` — additive extension for the frontend dev loop (does not break the consumer).
- `fixes/{idx}/simulate`: idx — index into the flat list of fixes across all findings
  (finding → proposed_changes, in order).
- Internal structured changes (`simulation.api.yaml` input) are kept in the store and
  do not extend the public `GET /investigations/{id}` response.
