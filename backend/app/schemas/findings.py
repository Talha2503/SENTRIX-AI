from pydantic import BaseModel


class FindingOut(BaseModel):
    id: int
    claim_id: int | None = None
    agent_name: str
    category: str
    title: str
    explanation: str
    severity: str
    status: str
    verification_status: str
    confidence: float | None = None
    confidence_notes: str | None = None
    recommended_followup: str | None = None
    evidence_ids: list[int] = []