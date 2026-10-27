"""Markdown report generation (GET /api/investigations/{id}/report.md)."""
from __future__ import annotations

from typing import Any

from .findings import Finding, VerifierReport, flat_fix_index, flatten_fixes


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
                sim = (meta.get("simulations") or {}).get(str(idx))
                badge = ""
                if sim:
                    verdict = sim["result"]
                    badge = (" ✅ **verified**" if verdict.get("verified")
                             else " ⚠️ **unverified suggestion**")
                lines.append(f"{j}. {c}{badge}")
                if sim:
                    lines.extend(_sim_table(sim))
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
    lines.append("## Plain English")
    lines.append("")
    sims = meta.get("simulations") or {}
    verified = [(idx, s) for idx, s in sims.items() if s["result"].get("verified")]
    if findings:
        top = findings[0]
        lines.append(f"The most likely reason is: {top.cause[0].lower() + top.cause[1:] if top.cause else ''} "
                     f"(confidence {top.confidence:.0%}, backed by {len(top.evidence)} data point(s) above).")
    if verified:
        idx, s = verified[0]
        fx = _fix_by_index(findings, int(idx))
        delta = s["result"]["after"]["impressions"] - s["result"]["before"]["impressions"]
        pct = (delta / s["result"]["before"]["impressions"] * 100
               if s["result"]["before"]["impressions"] else 0)
        lines.append("")
        lines.append(f"Tested fix: {fx or 'proposed change'} — the simulator projects delivery "
                     f"to change by {pct:+.0f}% ({delta:+,} impressions) without breaking constraints, "
                     f"so it is marked **verified**.")
    elif sims:
        lines.append("")
        lines.append("Tested fixes did not clear the verification threshold — they are shown as "
                     "unverified suggestions, not recommendations.")
    else:
        lines.append("")
        lines.append("No fixes have been simulated yet.")
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


def _fix_by_index(findings: list[Finding], flat_index: int) -> str | None:
    fixes = flatten_fixes(findings)
    for fx in fixes:
        if fx["index"] == flat_index:
            return fx["description"]
    return None


_METRIC_ROWS = ("impressions", "spend", "win_rate", "ecpm")


def _fmt(metric: str, v: Any) -> str:
    if metric == "impressions":
        return f"{v:,}"
    if metric == "win_rate":
        return f"{v:.1%}"
    return f"${v:,.2f}"


def _sim_table(sim: dict[str, Any]) -> list[str]:
    r = sim["result"]
    rows = ["", "| metric | before | after | delta |", "|---|---:|---:|---:|"]
    for m in _METRIC_ROWS:
        b, a = r["before"].get(m), r["after"].get(m)
        d = r["delta"].get(m)
        if b is None or a is None or d is None:
            continue
        rows.append(f"| {m} | {_fmt(m, b)} | {_fmt(m, a)} | {_fmt(m, d)} |")
    if r.get("violated_constraints"):
        rows.append("")
        rows.append(f"⚠️ constraints: {'; '.join(r['violated_constraints'])}")
    rows.append(f"_seed={sim['request'].get('seed')}, target={sim['request'].get('target_metric')}, "
                f"threshold={r.get('threshold_pct')}%_")
    return rows
