"""Investigation runner: the agent loop.

Modes:
- "llm": Muse Spark with native tool calling; on missing/failed tool calling
  falls back to structured-JSON prompting (PRD risk mitigation), then to
  heuristics if the model is unavailable entirely.
- "heuristic": deterministic rule engine over the same tools (offline demo,
  eval baseline; also the healthy-control guard).

Every tool call goes through ToolRegistry so the evidence ledger
(registry.executed refs) reflects real executions only.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Any, Callable

from ..config import Settings
from ..tools import TOOL_SPECS, ToolRegistry
from ..tools.base import ToolError
from . import heuristics
from .findings import Finding, enforce_evidence
from .llm import LLMParseError, LLMUnavailableError, MuseSparkClient, extract_json

TraceSink = Callable[[str, str | None, str, str], None]

SYSTEM_PROMPT = """You are Campaign Doctor, an ad-ops diagnostic agent.
You investigate why a campaign underdelivers or overspends, using ONLY the
data tools provided. Rules you must obey:
1. Never state a cause without citing at least one tool result as evidence
   (the pipeline will delete unsupported claims).
2. Investigate before concluding: check settings, delivery (day and hour),
   bid samples (outcome shares, seller split), and the healthy-control
   benchmark before forming findings.
3. Consider the known failure library: bid below market, targeting too
   narrow, frequency cap too strict, daypart mismatch, aggressive pacing,
   floor conflicts, low-quality supply path.
4. If the data shows no problem, say so plainly ("no major issue") and do
   NOT invent one.
5. Reply ONLY with minified JSON in the final answer, shaped as:
   {"findings": [{"cause": str, "evidence": [{"tool": str, "ref": str, "summary": str}],
   "confidence": 0..1, "proposed_changes": [str]}]}
   where each `ref` must exactly equal a ref returned by a tool call above.
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class InvestigationRunner:
    def __init__(self, settings: Settings, registry: ToolRegistry, trace: TraceSink):
        self.settings = settings
        self.registry = registry
        self.trace = trace

    # ------------------------------ heuristic ------------------------------ #
    def run_heuristic(self, campaign_id: str, question: str) -> list[Finding]:
        plan: list[tuple[str, dict[str, Any]]] = [
            ("get_campaign_settings", {"campaign_id": campaign_id}),
            ("query_delivery", {"campaign_id": campaign_id, "group_by": "day"}),
            ("query_delivery", {"campaign_id": campaign_id, "group_by": "hour"}),
            ("query_bid_samples", {"campaign_id": campaign_id, "group_by": "outcome"}),
            ("query_bid_samples", {"campaign_id": campaign_id, "group_by": "seller"}),
            ("compare_to_benchmark", {"campaign_id": campaign_id, "metric": "impressions"}),
        ]
        self.trace("plan", None, question,
                   "heuristic plan: settings -> delivery(day,hour) -> bid samples(outcome,seller) -> benchmark")
        ctx: dict[str, Any] = {}
        key_map = {
            "get_campaign_settings": "settings",
            "query_delivery:day": "delivery_day",
            "query_delivery:hour": "delivery_hour",
            "query_bid_samples:outcome": "bids_outcome",
            "query_bid_samples:seller": "bids_seller",
            "compare_to_benchmark": "benchmark",
        }
        for name, args in plan:
            res = self._safe_call(name, args)
            if res is None:
                continue
            lookup = f"{name}:{args.get('group_by')}" if args.get("group_by") else name
            key = key_map.get(lookup) or lookup
            ctx[key] = {"data": res.data, "summary": res.summary}
        self.trace("analyze", None, "rule engine over collected tool outputs",
                   "candidate findings from PRD §8 failure-mode library")
        return heuristics.analyze(ctx, campaign_id)

    # --------------------------------- llm --------------------------------- #
    def run_llm(self, client: MuseSparkClient, campaign_id: str, question: str) -> tuple[list[Finding], str]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Campaign: {campaign_id}\nQuestion: {question}"},
        ]
        mode = "tool-calling"
        for step in range(self.settings.agent_max_steps):
            resp = client.chat(messages, tools=TOOL_SPECS if mode == "tool-calling" else None)
            if resp.wants_tool:
                messages.append({"role": "assistant", "content": None, "tool_calls": resp.raw["choices"][0]["message"]["tool_calls"]})
                for call in resp.tool_calls:
                    res = self._safe_call(call["name"], call["arguments"])
                    if res is None:
                        continue
                    messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                     "content": json.dumps({"ref": res.ref, "summary": res.summary,
                                                            "data": _clip(res.data)}, ensure_ascii=False)})
                continue
            # no tool calls: try final JSON; if it's a step-action JSON, honor it (fallback mode)
            text = resp.content or ""
            try:
                payload = extract_json(text)
            except LLMParseError:
                if mode == "tool-calling" and step == 0:
                    self.trace("fallback", None, "model reply without tool_calls",
                               "switching to structured-JSON prompting (PRD fallback)")
                    mode = "json-prompting"
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content":
                                     'Reply ONLY with JSON: {"tool": "<tool name>", "arguments": {...}} '
                                     "for the next tool call, or the final {\"findings\": [...]} object. "
                                     "Evidence refs must match refs returned by tools."})
                    continue
                raise
            if isinstance(payload, dict) and "findings" in payload:
                findings = _parse_findings(payload["findings"])
                self.trace("analyze", None, f"final findings JSON ({len(findings)} candidates)",
                           "; ".join(f.cause[:60] for f in findings[:3]))
                return findings, mode
            if isinstance(payload, dict) and payload.get("tool"):
                messages.append({"role": "assistant", "content": text})
                res = self._safe_call(str(payload["tool"]), payload.get("arguments") or {})
                if res is not None:
                    messages.append({"role": "user", "content": json.dumps(
                        {"ref": res.ref, "summary": res.summary, "data": _clip(res.data)}, ensure_ascii=False)})
                continue
            raise LLMParseError("model JSON matched neither findings nor tool action")
        raise RuntimeError(f"agent exceeded max steps ({self.settings.agent_max_steps})")

    # -------------------------------- common ------------------------------- #
    def _safe_call(self, name: str, args: dict[str, Any]) -> Any:
        try:
            res = self.registry.call(name, args)
        except (ToolError, ValueError) as e:
            self.trace("tool", name, _clip(args), f"error: {e}")
            return None
        self.trace("tool", name, _clip(args), _clip(res.summary))
        return res

    def run(self, campaign_id: str, question: str) -> tuple[list[Finding], dict[str, Any]]:
        mode = "heuristic"
        findings: list[Finding] = []
        llm_note = ""
        if self.settings.llm_available:
            try:
                client = MuseSparkClient(self.settings.muse_base_url,  # type: ignore[arg-type]
                                         self.settings.muse_api_key,  # type: ignore[arg-type]
                                         self.settings.muse_model,
                                         self.settings.request_timeout_s)
                self.trace("plan", None, question, f"LLM mode: model={self.settings.muse_model}")
                findings, mode = self.run_llm(client, campaign_id, question)
            except (LLMUnavailableError, LLMParseError, RuntimeError, OSError) as e:
                llm_note = f"LLM unavailable/failed ({type(e).__name__}: {e}); heuristic fallback used"
                self.trace("fallback", None, type(e).__name__, llm_note)
                findings = self.run_heuristic(campaign_id, question)
        else:
            self.trace("plan", None, question,
                       "no Muse Spark credentials in env -> deterministic heuristic mode (offline demo)")
            findings = self.run_heuristic(campaign_id, question)

        kept, report = enforce_evidence(findings, self.registry.executed)
        self.trace("verify", None,
                   f"{report.claims_total} claims, {len(report.removed)} removed",
                   "; ".join(report.removed) or "all claims grounded")
        meta = {"agent_mode": mode, "llm_note": llm_note,
                "tool_calls": list(self.registry.executed.keys())}
        return kept, {"verifier": report, "meta": meta}


def _parse_findings(raw: Any) -> list[Finding]:
    from .findings import Evidence
    out: list[Finding] = []
    if not isinstance(raw, list):
        raise LLMParseError("findings must be a list")
    for item in raw:
        if not isinstance(item, dict) or "cause" not in item:
            continue
        ev = [Evidence(tool=str(e.get("tool", "")), ref=str(e.get("ref", "")),
                       summary=str(e.get("summary", "")))
              for e in item.get("evidence", []) if isinstance(e, dict)]
        out.append(Finding(
            cause=str(item["cause"]),
            evidence=ev,
            confidence=float(item.get("confidence", 0.5)),
            proposed_changes=[str(c) for c in item.get("proposed_changes", [])],
            changes=[c if isinstance(c, dict) else {} for c in item.get("changes", [])],
        ))
    return out


def _clip(x: Any, limit: int = 300) -> str:
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def run_investigation(store, settings: Settings, repo, campaign_id: str, question: str,
                      investigation_id: str) -> None:
    """Entry point executed in a worker thread; updates the store as it goes."""
    registry = ToolRegistry(repo, settings)

    def trace(step: str, tool: str | None, inp: str, outp: str) -> None:
        store.append_trace(investigation_id,
                           {"ts": _now(), "step": step, "tool": tool,
                            "input_summary": _clip(inp), "output_summary": _clip(outp)})

    runner = InvestigationRunner(settings, registry, trace)
    try:
        repo.get(campaign_id)  # fail fast on unknown campaign
        findings, extra = runner.run(campaign_id, question)
        store.complete(investigation_id, findings, extra)
    except ToolError as e:
        store.fail(investigation_id, str(e))
    except Exception as e:  # noqa: BLE001 - surfaced to the API caller
        traceback.print_exc()
        store.fail(investigation_id, f"{type(e).__name__}: {e}")
