from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Application, Assessment, Report
from app.schemas.report import AssessmentOut, ReportOut

router = APIRouter(prefix="/applications", tags=["report"])


def _check(db: Session, application_id: int) -> None:
    if db.get(Application, application_id) is None:
        raise HTTPException(404, "Application not found")


@router.get("/{application_id}/report", response_model=ReportOut)
def get_report(application_id: int, db: Session = Depends(get_db)):
    _check(db, application_id)
    report = db.scalars(
        select(Report).where(Report.application_id == application_id).order_by(Report.id.desc())
    ).first()
    if report is None:
        raise HTTPException(404, "No report yet. Run the investigation first.")
    return report


@router.get("/{application_id}/assessment", response_model=AssessmentOut)
def get_assessment(application_id: int, db: Session = Depends(get_db)):
    _check(db, application_id)
    assessment = db.scalars(
        select(Assessment).where(Assessment.application_id == application_id).order_by(Assessment.id.desc())
    ).first()
    if assessment is None:
        raise HTTPException(404, "No assessment yet. Run the investigation first.")
    return assessment