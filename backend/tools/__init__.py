"""Tool registry: single place mapping tool names to implementations.

The agent (LLM mode) and the heuristic engine both execute tools through
this registry so that evidence refs are always produced by real executions.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from ..config import Settings
from .base import ToolError, ToolResult
from .data_tools import (BENCHMARK_CAMPAIGN, compare_to_benchmark,
                         get_campaign_settings, query_bid_samples, query_delivery)
from .loader import DatasetRepository
from .sim_client import make_simulation_client

HandledCall = Callable[[str, dict[str, Any]], ToolResult]


class ToolRegistry:
    def __init__(self, repo: DatasetRepository, settings: Settings):
        self.repo = repo
        self.settings = settings
        self.sim = make_simulation_client(repo, settings)
        self.executed: dict[str, ToolResult] = {}  # ref -> result (evidence ledger)

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        args = args or {}
        r = self._dispatch(name, args)
        self.executed[r.ref] = r
        return r

    def _dispatch(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name == "query_delivery":
            return query_delivery(self.repo, args.get("campaign_id"),
                                  metric=args.get("metric"), group_by=args.get("group_by"),
                                  date_from=args.get("date_from"), date_to=args.get("date_to"))
        if name == "query_bid_samples":
            return query_bid_samples(self.repo, args.get("campaign_id"),
                                     group_by=args.get("group_by"),
                                     outcome=args.get("outcome"))
        if name == "get_campaign_settings":
            return get_campaign_settings(self.repo, args.get("campaign_id"))
        if name == "compare_to_benchmark":
            return compare_to_benchmark(self.repo, args.get("campaign_id"),
                                        metric=args.get("metric", "impressions"))
        if name == "run_simulation":
            out = self.sim.run_simulation(
                campaign_id=args.get("campaign_id"), seed=int(args.get("seed", 0)),
                changes=args.get("changes") or {}, constraints=args.get("constraints"),
                target_metric=args.get("target_metric", "impressions"))
            cid = args.get("campaign_id")
            return ToolResult(
                tool="run_simulation", ref=f"run_simulation:{cid}:{args.get('seed', 0)}",
                summary=(f"{cid}: delta_pct(impressions)={out['delta_pct']['impressions']}%, "
                         f"verified={out['verified']}, violated={out['violated_constraints']}"),
                data=out)
        raise ToolError(f"Unknown tool '{name}'. Registered: query_delivery, query_bid_samples, "
                        f"get_campaign_settings, compare_to_benchmark, run_simulation.")


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_delivery",
            "description": "Aggregate delivery stats (impressions, spend, bids, wins) by day or by hour for a campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "metric": {"type": "string", "enum": ["impressions", "spend", "bids", "wins"]},
                    "group_by": {"type": "string", "enum": ["day", "hour"]},
                    "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_bid_samples",
            "description": "Inspect the anonymized bid-request sample: outcome shares (win/loss_outbid/loss_below_floor/dropped_*), loss gaps, seller/geo/device splits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "group_by": {"type": "string", "enum": ["outcome", "seller", "geo", "device"]},
                    "outcome": {"type": "string",
                                "enum": ["win", "loss_below_floor", "loss_outbid",
                                         "dropped_freq_cap", "dropped_targeting"]},
                },
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_settings",
            "description": "Read campaign configuration: budget, flight dates, pacing, bid, targeting, frequency cap, dayparts, auction model.",
            "parameters": {
                "type": "object",
                "properties": {"campaign_id": {"type": "string"}},
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_to_benchmark",
            "description": "Compare a campaign metric against the healthy control campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "metric": {"type": "string", "enum": ["impressions", "spend", "bids", "wins"]},
                },
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_simulation",
            "description": "Replay proposed setting changes in the auction simulator; returns before/after metrics and verification verdict.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "seed": {"type": "integer"},
                    "changes": {"type": "object"},
                    "constraints": {"type": "object"},
                    "target_metric": {"type": "string", "enum": ["impressions", "spend", "win_rate", "ecpm"]},
                },
                "required": ["campaign_id"],
            },
        },
    },
]


def specs_json() -> str:
    return json.dumps(TOOL_SPECS, ensure_ascii=False)
