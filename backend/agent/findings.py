"""Findings model + the code-level evidence rule (PRD 6.2, zone AGENTS.md).

"No evidence from a tool -> no diagnosis" is enforced HERE, in code:
a finding whose evidence refs do not match actually executed tool results
is removed and reported in `verifier.removed`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evidence:
    tool: str
    ref: str
    summary: str


@dataclass
class Finding:
    cause: str
    evidence: list[Evidence]
    confidence: float
    proposed_changes: list[str] = field(default_factory=list)
    # structured changes mirror proposed_changes 1:1 (simulation.api.yaml `changes`);
    # internal only, not part of the public API response.
    changes: list[dict[str, Any]] = field(default_factory=list)

    def to_api(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "evidence": [{"tool": e.tool, "ref": e.ref, "summary": e.summary} for e in self.evidence],
            "confidence": round(float(self.confidence), 3),
            "proposed_changes": list(self.proposed_changes),
        }


@dataclass
class VerifierReport:
    claims_total: int = 0
    claims_grounded: int = 0
    removed: list[str] = field(default_factory=list)

    def to_api(self) -> dict[str, Any]:
        return {
            "claims_total": self.claims_total,
            "claims_grounded": self.claims_grounded,
            "removed": list(self.removed),
        }


def flatten_fixes(findings: list[Finding]) -> list[dict[str, Any]]:
    """Flatten (finding, change) pairs across all findings; index = position here."""
    out: list[dict[str, Any]] = []
    for fi, f in enumerate(findings):
        for ci, desc in enumerate(f.proposed_changes):
            structured = f.changes[ci] if ci < len(f.changes) else {}
            out.append({"index": len(out), "finding_index": fi, "change_index": ci,
                        "description": desc, "changes": structured})
    return out


def flat_fix_index(findings: list[Finding], finding_index: int, change_index: int) -> int:
    return sum(len(f.proposed_changes) for f in findings[:finding_index]) + change_index


def enforce_evidence(findings: list[Finding], executed_refs: dict[str, Any]) -> tuple[list[Finding], VerifierReport]:
    """Keep only findings whose every evidence ref was produced by a real tool call."""
    kept: list[Finding] = []
    report = VerifierReport()
    for f in findings:
        report.claims_total += 1
        valid_evidence = [e for e in f.evidence if e.ref in executed_refs]
        if not f.evidence or len(valid_evidence) != len(f.evidence):
            bad_refs = sorted({e.ref for e in f.evidence if e.ref not in executed_refs})
            report.removed.append(
                f"removed claim '{f.cause[:80]}': evidence not found among executed tool "
                f"results (missing refs: {', '.join(bad_refs) if bad_refs else 'no evidence provided'})")
            continue
        f.evidence = valid_evidence
        report.claims_grounded += 1
        kept.append(f)
    return kept, report
