from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    task: str | None = None
    status: str
    error: str | None = None
    output: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int | None = None
    chunk_id: int | None = None
    claim_text: str
    source_quote: str | None = None
    category: str
    value: float | None = None
    unit: str | None = None
    reporting_period: str | None = None
    baseline_period: str | None = None
    page_number: int | None = None
    status: str
    extraction_method: str | None = None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int | None = None
    chunk_id: int | None = None
    claim_id: int | None = None
    page_number: int | None = None
    excerpt: str | None = None
    evidence_type: str
    metric: str | None = None
    value: float | None = None
    unit: str | None = None
    reporting_period: str | None = None
    extraction_method: str | None = None


class InvestigationOut(BaseModel):
    application_id: int
    status: str
    claim_count: int
    evidence_count: int
    agent_runs: list[AgentRunOut]