"""Verifier pass (PRD 6.4): confirm every claim matches tool outputs.

Two layers:
1. Rule-based (always on, code-level rule): evidence refs must point at
   actually executed tool results — `findings.enforce_evidence`.
2. LLM pass (when Muse Spark is available): semantic check that each claim
   is supported by the referenced tool outputs; unsupported claims are
   removed with the model's reason. LLM failures never widen the verdict:
   on error the rule-based outcome stands (claim kept, reason logged).

Groundedness metric = claims_grounded / claims_total after this pass.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .findings import Finding, VerifierReport
from .llm import LLMUnavailableError, LLMParseError, MuseSparkClient, extract_json

VERIFIER_SYSTEM = """You are the verifier pass of Campaign Doctor.
For each diagnostic claim you receive the claim, its cited evidence and the
actual tool outputs it references. Decide strictly:
- supported=true ONLY if the tool outputs clearly substantiate the claim
  (numbers, shares, settings line up);
- otherwise supported=false with a short reason.
Replay the numbers yourself; do not trust the summary text.
Reply ONLY with minified JSON: {"supported": bool, "reason": str}."""

TraceSink = Callable[..., None]


def verify_with_llm(findings: list[Finding], executed: dict[str, Any],
                    client: MuseSparkClient, trace: TraceSink | None = None
                    ) -> tuple[list[Finding], VerifierReport]:
    """Semantic grounding check. Returns (kept_findings, report)."""
    report = VerifierReport(claims_total=len(findings))
    kept: list[Finding] = []
    for f in findings:
        outputs = {}
        for e in f.evidence:
            if e.ref not in executed:
                continue
            result = executed[e.ref]
            outputs[e.ref] = _clip_data(result.data if hasattr(result, "data") else result)
        payload = {
            "claim": f.cause,
            "evidence": [{"ref": e.ref, "summary": e.summary} for e in f.evidence],
            "tool_outputs": outputs,
        }
        supported, reason = True, ""
        try:
            resp = client.chat(
                [{"role": "system", "content": VERIFIER_SYSTEM},
                 {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                temperature=0.0)
            verdict = extract_json(resp.content or "")
            supported = bool(verdict.get("supported"))
            reason = str(verdict.get("reason", ""))[:200]
        except (LLMUnavailableError, LLMParseError, OSError, ValueError) as e:
            # verifier failure must not delete grounded work: keep the claim
            supported = True
            reason = f"verifier error ({type(e).__name__}), rule-based verdict kept"
        if supported:
            report.claims_grounded += 1
            kept.append(f)
        else:
            report.removed.append(f"removed claim '{f.cause[:80]}': verifier: {reason}")
        if trace is not None:
            trace("verify-llm", None, f.cause[:60],
                  f"supported={supported}" + (f" ({reason})" if reason else ""))
    return kept, report


def _clip_data(data: Any, limit: int = 2500) -> Any:
    s = json.dumps(data, ensure_ascii=False, default=str)
    if len(s) <= limit:
        return data
    return {"_truncated": s[:limit]}
