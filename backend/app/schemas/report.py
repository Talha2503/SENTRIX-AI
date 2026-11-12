from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    summary: str | None = None
    content: dict | None = None
    review_status: str
    created_at: datetime


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    calculation_version: str
    dimension_scores: dict | None = None
    coverage: dict | None = None
    overall_confidence: float | None = None
    limitations: str | None = None
    created_at: datetime