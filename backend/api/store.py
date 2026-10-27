"""Thread-safe investigation store with JSONL trace persistence.

State lives in memory (demo-local scope per contract: no auth, single node);
every completed investigation is also dumped to state_dir for auditability
(PRD 6.4: full trace log per investigation, viewable in the UI).
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..agent.findings import Finding, VerifierReport, flatten_fixes


class Investigation:
    def __init__(self, investigation_id: str, campaign_id: str, question: str):
        self.id = investigation_id
        self.campaign_id = campaign_id
        self.question = question
        self.status: str = "running"
        self.trace: list[dict[str, Any]] = []
        self.findings: list[Finding] = []
        self.verifier: VerifierReport | None = None
        self.meta: dict[str, Any] = {}
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()

    def fixes(self) -> list[dict[str, Any]]:
        return flatten_fixes(self.findings)


class InvestigationStore:
    def __init__(self, state_dir: Path | None = None):
        self._lock = threading.Lock()
        self._items: dict[str, Investigation] = {}
        self._state_dir = state_dir

    def create(self, campaign_id: str, question: str) -> Investigation:
        inv = Investigation(uuid.uuid4().hex[:12], campaign_id, question)
        with self._lock:
            self._items[inv.id] = inv
        return inv

    def get(self, investigation_id: str) -> Investigation | None:
        with self._lock:
            return self._items.get(investigation_id)

    def append_trace(self, investigation_id: str, step: dict[str, Any]) -> None:
        with self._lock:
            inv = self._items.get(investigation_id)
            if inv is None:
                return
            inv.trace.append(step)
        if self._state_dir is not None:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            with (self._state_dir / f"{investigation_id}.trace.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(step, ensure_ascii=False) + "\n")

    def complete(self, investigation_id: str, findings: list[Finding],
                 extra: dict[str, Any]) -> None:
        with self._lock:
            inv = self._items.get(investigation_id)
            if inv is None:
                return
            inv.findings = findings
            inv.verifier = extra.get("verifier")
            inv.meta = extra.get("meta", {})
            inv.status = "done"
            snapshot = self._snapshot(inv)
        self._persist(investigation_id, snapshot)

    def fail(self, investigation_id: str, message: str) -> None:
        with self._lock:
            inv = self._items.get(investigation_id)
            if inv is None:
                return
            inv.status = "error"
            inv.error = message
            snapshot = self._snapshot(inv)
        self._persist(investigation_id, snapshot)

    def record_simulation(self, investigation_id: str, fix_index: int,
                          request: dict[str, Any], result: dict[str, Any]) -> None:
        with self._lock:
            inv = self._items.get(investigation_id)
            if inv is None:
                return
            sims = inv.meta.setdefault("simulations", {})
            sims[str(fix_index)] = {"request": request, "result": result}
            snapshot = self._snapshot(inv)
        self._persist(investigation_id, snapshot)

    def _snapshot(self, inv: Investigation) -> dict[str, Any]:
        return {
            "id": inv.id, "campaign_id": inv.campaign_id, "question": inv.question,
            "status": inv.status, "created_at": inv.created_at,
            "trace": inv.trace,
            "findings": [f.to_api() for f in inv.findings],
            "verifier": inv.verifier.to_api() if inv.verifier else None,
            "meta": inv.meta, "error": inv.error,
            "fixes": [{"index": fx["index"], "description": fx["description"], "changes": fx["changes"]}
                      for fx in inv.fixes()],
        }

    def _persist(self, investigation_id: str, snapshot: dict[str, Any]) -> None:
        if self._state_dir is None:
            return
        self._state_dir.mkdir(parents=True, exist_ok=True)
        (self._state_dir / f"{investigation_id}.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
