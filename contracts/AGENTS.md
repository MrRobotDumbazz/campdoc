# AGENTS.md — /contracts (the seam)

You are under ZTACP. Canon: ../docs/ztacp-pattern.md (v1.0-rc15). Constitution: ../AGENTS.md.

**Writer-owner:** S-1 (coordinator) only. Zones A and B are readers and consumers.
**Rule (I4/B1):** only the owner changes a contract; breaking changes ship as a new version, never as an edit. Amendments are dual-key (I22): S-1 prepares, P-1 signs.
**Mocks (B2):** zone A works from `simulation.api.yaml` through a mock; zone B implements against the same file. Nobody waits for a neighbour.
**To you as a worker:** everything here belongs to someone else unless you are S-1 — refuse and point to the owner (C4).
