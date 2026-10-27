"""FastAPI app implementing /contracts/app.api.yaml (v1-draft).

Endpoints:
  GET  /api/datasets
  POST /api/ask                                              -> 202 {investigation_id}
  GET  /api/investigations/{id}                              -> status/trace/findings/verifier
  POST /api/investigations/{id}/fixes/{idx}/simulate         -> simulation.api.yaml output
  GET  /api/investigations/{id}/report.md                    -> text/markdown
Extension (additive, documented): GET /api/health for the frontend's dev loop.
"""
from __future__ import annotations

import threading
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from ..agent.findings import VerifierReport
from ..agent.report import build_report
from ..agent.runner import run_investigation
from ..config import Settings, get_settings
from ..tools import make_simulation_client
from ..tools.base import ToolError
from ..tools.loader import DatasetRepository
from .schemas import (AskRequest, AskResponse, DatasetItem, DatasetsResponse,
                      ErrorResponse, InvestigationOut, SimulateRequest,
                      SimulateResponse)
from .store import InvestigationStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    repo = DatasetRepository(settings.data_dir)
    store = InvestigationStore(settings.state_dir / "investigations")
    sim = make_simulation_client(repo, settings)

    app = FastAPI(title="Campaign Doctor API", version="0.1.0",
                  description="Verifiable ad-campaign diagnostics (hackathon build)")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                       allow_headers=["*"])

    def _err(status: int, error: str, detail: str | None = None):
        return JSONResponse(status_code=status, content=ErrorResponse(error=error, detail=detail).model_dump())

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "agent_mode": "llm" if settings.llm_available else "heuristic",
                "data_source": "mock" if repo.using_mock_data() else "data-dir",
                "simulator": sim.name}

    @app.get("/api/datasets", response_model=DatasetsResponse)
    def datasets() -> DatasetsResponse:
        try:
            items = [DatasetItem(**c) for c in repo.list_campaigns()]
        except ToolError as e:
            raise HTTPException(422, str(e))
        return DatasetsResponse(datasets=items)

    @app.post("/api/ask", response_model=AskResponse, status_code=202)
    def ask(req: AskRequest) -> JSONResponse:
        try:
            repo.get(req.campaign_id)
        except ToolError as e:
            return _err(404, "unknown campaign", str(e))
        inv = store.create(req.campaign_id, req.question)
        t = threading.Thread(target=run_investigation,
                             args=(store, settings, repo, req.campaign_id,
                                   req.question, inv.id),
                             daemon=True)
        t.start()
        return JSONResponse(status_code=202, content=AskResponse(investigation_id=inv.id).model_dump())

    @app.get("/api/investigations/{investigation_id}", response_model=InvestigationOut)
    def investigation(investigation_id: str) -> InvestigationOut:
        inv = store.get(investigation_id)
        if inv is None:
            raise HTTPException(404, "unknown investigation")
        return InvestigationOut(
            status=inv.status,  # type: ignore[arg-type]
            question=inv.question,
            trace=inv.trace,  # type: ignore[arg-type]
            findings=[f.to_api() for f in inv.findings] if inv.status == "done" else None,
            verifier=inv.verifier.to_api() if (inv.status == "done" and inv.verifier) else None,
            error=inv.error)

    @app.post("/api/investigations/{investigation_id}/fixes/{idx}/simulate",
              response_model=SimulateResponse)
    def simulate_fix(investigation_id: str, idx: int, req: SimulateRequest) -> SimulateResponse:
        inv = store.get(investigation_id)
        if inv is None:
            raise HTTPException(404, "unknown investigation")
        if inv.status != "done":
            return _err(409, "investigation not finished", f"status={inv.status}")  # type: ignore[return-value]
        fixes = inv.fixes()
        if not 0 <= idx < len(fixes):
            return _err(404, "unknown fix index", f"valid range 0..{len(fixes) - 1}")  # type: ignore[return-value]
        fx = fixes[idx]
        try:
            out = sim.run_simulation(campaign_id=inv.campaign_id, seed=req.seed,
                                     changes=fx["changes"], constraints=req.constraints,
                                     target_metric=req.target_metric)
        except ToolError as e:
            return _err(422, "simulation failed", str(e))  # type: ignore[return-value]
        store.record_simulation(investigation_id, idx,
                                {"seed": req.seed, "target_metric": req.target_metric,
                                 "description": fx["description"]}, out)
        return SimulateResponse(**{k: out[k] for k in
                                   ("before", "after", "delta", "verified", "threshold_pct",
                                    "violated_constraints", "notes")})

    @app.get("/api/investigations/{investigation_id}/report.md")
    def report_md(investigation_id: str):
        inv = store.get(investigation_id)
        if inv is None:
            raise HTTPException(404, "unknown investigation")
        if inv.status != "done":
            content = (f"# Campaign Doctor — report pending\n\n"
                       f"Investigation `{investigation_id}` is `{inv.status}`."
                       + (f"\n\nError: {inv.error}" if inv.error else ""))
            return PlainTextResponse(content, media_type="text/markdown")
        content = build_report(
            {"id": inv.id, "question": inv.question, "campaign_id": inv.campaign_id, "trace": inv.trace},
            inv.findings, inv.verifier or VerifierReport(), inv.meta)
        return PlainTextResponse(content, media_type="text/markdown")

    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        return _err(exc.status_code, exc.detail if isinstance(exc.detail, str) else "error")

    return app


app = create_app()
