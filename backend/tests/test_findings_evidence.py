"""The code-level evidence rule (PRD 6.2): no tool evidence -> no diagnosis."""
from __future__ import annotations

from backend.agent.findings import Evidence, Finding, enforce_evidence


def test_finding_without_evidence_is_removed():
    findings = [Finding(cause="gremlins in the DSP", evidence=[], confidence=0.9)]
    kept, report = enforce_evidence(findings, {"some:ref": object()})
    assert kept == []
    assert report.claims_total == 1
    assert report.claims_grounded == 0
    assert "gremlins" in report.removed[0]


def test_finding_with_fabricated_ref_is_removed():
    findings = [Finding(cause="bid too low", confidence=0.9,
                        evidence=[Evidence(tool="query_bid_samples", ref="made:up", summary="x")])]
    kept, report = enforce_evidence(findings, {"real:ref": object()})
    assert kept == []
    assert "made:up" in report.removed[0]


def test_finding_with_executed_refs_is_kept():
    findings = [Finding(cause="bid too low", confidence=0.9,
                        evidence=[Evidence(tool="query_bid_samples", ref="a:b", summary="x")])]
    kept, report = enforce_evidence(findings, {"a:b": object()})
    assert len(kept) == 1
    assert report.claims_grounded == 1
    assert report.removed == []


def test_mixed_findings_split():
    findings = [
        Finding(cause="ok claim", confidence=0.8,
                evidence=[Evidence(tool="t", ref="r1", summary="s")]),
        Finding(cause="bad claim", confidence=0.8,
                evidence=[Evidence(tool="t", ref="ghost", summary="s")]),
    ]
    kept, report = enforce_evidence(findings, {"r1": object()})
    assert [f.cause for f in kept] == ["ok claim"]
    assert report.claims_total == 2
    assert report.claims_grounded == 1
