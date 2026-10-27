"""Pydantic models mirroring /contracts/app.api.yaml exactly."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DatasetItem(BaseModel):
    campaign_id: str
    name: str
    healthy: bool


class DatasetsResponse(BaseModel):
    datasets: list[DatasetItem]


class AskRequest(BaseModel):
    campaign_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    investigation_id: str


class TraceStep(BaseModel):
    ts: str
    step: str
    tool: str | None = None
    input_summary: str
    output_summary: str


class EvidenceItem(BaseModel):
    tool: str
    ref: str
    summary: str


class FindingOut(BaseModel):
    cause: str
    evidence: list[EvidenceItem]
    confidence: float = Field(ge=0, le=1)
    proposed_changes: list[str]


class VerifierOut(BaseModel):
    claims_total: int
    claims_grounded: int
    removed: list[str]


class InvestigationOut(BaseModel):
    status: Literal["running", "done", "error"]
    question: str
    trace: list[TraceStep] = []
    findings: list[FindingOut] | None = None
    verifier: VerifierOut | None = None
    error: str | None = None  # present when status=error


class SimulateRequest(BaseModel):
    seed: int = 0
    target_metric: Literal["impressions", "spend", "win_rate", "ecpm"] = "impressions"
    constraints: dict | None = None


class Metrics(BaseModel):
    impressions: int
    spend: float
    win_rate: float
    ecpm: float


class SimulateResponse(BaseModel):
    before: Metrics
    after: Metrics
    delta: Metrics
    verified: bool
    threshold_pct: float
    violated_constraints: list[str]
    notes: list[str]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
