# AGENTS.md — zone "data" (synthetic data, W-3)

You are under ZTACP. Canon: ../docs/ztacp-pattern.md (v1.0-rc15). Constitution: ../AGENTS.md.

**Owner:** W-3 (Codex, supervisor — P-2). **Your zone:** generators for 6–8 synthetic campaigns + a healthy control.

## Boundaries
- Formats — strictly per /contracts/data.schemas.md; the generator must produce data that passes consumer validation.
- Seeded failure modes — all PRD §8 modes (1–8); seeds fixed in data/manifest.json for eval reproducibility.
- Pseudonymization: site_app/seller are pseudonyms; no real publishers, no personal data (I44).
- Write only here and in /simulator. Commit: `data: <what>` (C5).

## Rules
- A claim without evidence = P5 (E8). Rights R1–R5 — constitution §7.
