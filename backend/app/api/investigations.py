from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.graph import run_investigation
from app.core.database import SessionLocal, get_db
from app.models.models import AgentRun, Application, Claim, Evidence
from app.schemas.investigation import (
    AgentRunOut,
    ClaimOut,
    EvidenceOut,
    InvestigationOut,
)

router = APIRouter(prefix="/applications", tags=["investigation"])


def _get_application(db: Session, application_id: int) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    return application


def _run_in_background(application_id: int) -> None:
    try:
        run_investigation(application_id)
    except Exception as exc:
        with SessionLocal() as db:
            application = db.get(Application, application_id)
            if application:
                application.status = "failed"
            db.add(
                AgentRun(
                    application_id=application_id,
                    agent_name="orchestrator",
                    task="investigation",
                    status="failed",
                    error=str(exc)[:1000],
                )
            )
            db.commit()


@router.post("/{application_id}/investigate", status_code=202)
def start_investigation(
    application_id: int,
    background: BackgroundTasks,
    force: bool = False,
    db: Session = Depends(get_db),
):
    application = _get_application(db, application_id)
    if application.status == "investigating" and not force:
        raise HTTPException(409, "An investigation is already running. Use ?force=true to restart.")
    application.status = "investigating"
    db.commit()
    background.add_task(_run_in_background, application_id)
    return {"application_id": application_id, "status": "investigating"}


@router.get("/{application_id}/investigation", response_model=InvestigationOut)
def get_investigation(application_id: int, db: Session = Depends(get_db)):
    application = _get_application(db, application_id)
    runs = db.scalars(
        select(AgentRun).where(AgentRun.application_id == application_id).order_by(AgentRun.id)
    ).all()
    claim_count = db.scalar(select(func.count()).select_from(Claim).where(Claim.application_id == application_id))
    evidence_count = db.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.application_id == application_id)
    )
    return InvestigationOut(
        application_id=application_id,
        status=application.status,
        claim_count=claim_count or 0,
        evidence_count=evidence_count or 0,
        agent_runs=[AgentRunOut.model_validate(r) for r in runs],
    )


@router.get("/{application_id}/claims", response_model=list[ClaimOut])
def list_claims(application_id: int, db: Session = Depends(get_db)):
    _get_application(db, application_id)
    return db.scalars(select(Claim).where(Claim.application_id == application_id).order_by(Claim.id)).all()


@router.get("/{application_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(application_id: int, metric: str | None = None, db: Session = Depends(get_db)):
    _get_application(db, application_id)
    stmt = select(Evidence).where(Evidence.application_id == application_id)
    if metric:
        stmt = stmt.where(Evidence.metric == metric)
    return db.scalars(stmt.order_by(Evidence.id)).all()