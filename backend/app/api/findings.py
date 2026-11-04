from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Application, Finding
from app.schemas.findings import FindingOut

router = APIRouter(prefix="/applications", tags=["findings"])


@router.get("/{application_id}/findings", response_model=list[FindingOut])
def list_findings(application_id: int, db: Session = Depends(get_db)):
    if db.get(Application, application_id) is None:
        raise HTTPException(404, "Application not found")
    findings = db.scalars(
        select(Finding).where(Finding.application_id == application_id).order_by(Finding.id)
    ).all()
    return [
        FindingOut(
            id=f.id,
            claim_id=f.claim_id,
            agent_name=f.agent_name,
            category=f.category,
            title=f.title,
            explanation=f.explanation,
            severity=f.severity,
            status=f.status,
            verification_status=f.verification_status,
            confidence=f.confidence,
            confidence_notes=f.confidence_notes,
            recommended_followup=f.recommended_followup,
            evidence_ids=[e.id for e in f.evidence_items],
        )
        for f in findings
    ]