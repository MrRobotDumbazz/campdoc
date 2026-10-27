"""Markdown report generation (GET /api/investigations/{id}/report.md)."""
from __future__ import annotations

from typing import Any

from .findings import Finding, VerifierReport, flat_fix_index


def build_report(investigation: dict[str, Any], findings: list[Finding],
                 verifier: VerifierReport, meta: dict[str, Any]) -> str:
    lines: list[str] = []
    q = investigation.get("question", "")
    cid = investigation.get("campaign_id", "")
    lines.append(f"# Campaign Doctor — Diagnosis Report")
    lines.append("")
    lines.append(f"- **Campaign:** `{cid}`")
    lines.append(f"- **Question:** {q}")
    lines.append(f"- **Investigation:** `{investigation.get('id')}`")
    lines.append(f"- **Agent mode:** {meta.get('agent_mode', 'heuristic')}"
                 + (f" ({meta.get('llm_note')})" if meta.get("llm_note") else ""))
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if not findings:
        lines.append("_No grounded findings were produced (all claims lacked tool evidence)._")
    for i, f in enumerate(findings, start=1):
        lines.append(f"### {i}. {f.cause}")
        lines.append(f"**Confidence:** {f.confidence:.0%}")
        lines.append("")
        lines.append("**Evidence:**")
        for e in f.evidence:
            lines.append(f"- `{e.tool}` — {e.summary} _(ref: `{e.ref}`)_")
        if f.proposed_changes:
            lines.append("")
            lines.append("**Proposed changes:**")
            for j, c in enumerate(f.proposed_changes, start=1):
                idx = flat_fix_index(findings, i - 1, j - 1)
                lines.append(f"{j}. {c} _(run POST /api/investigations/{investigation.get('id')}/fixes/{idx}/simulate to verify)_")
        lines.append("")
    lines.append("## Verifier")
    lines.append("")
    g = verifier.claims_grounded
    t = verifier.claims_total
    pct = f"{g / t:.0%}" if t else "n/a"
    lines.append(f"- Claims: **{g}/{t} grounded ({pct})**")
    if verifier.removed:
        for r in verifier.removed:
            lines.append(f"- ✂️ {r}")
    else:
        lines.append("- No unsupported claims were removed.")
    lines.append("")
    lines.append("## Tool trace")
    lines.append("")
    for s in investigation.get("trace", []):
        tool = f" `{s['tool']}`" if s.get("tool") else ""
        lines.append(f"- `{s['ts']}` {s['step']}{tool}: {s['output_summary']}")
    lines.append("")
    lines.append("---")
    lines.append("_Simulation results are forecasts on sampled data, not guarantees._")
    return "\n".join(lines)
