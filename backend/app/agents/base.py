from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.models import (
    AgentRun,
    Assessment,
    Claim,
    Evidence,
    Finding,
    Report,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_agent(
    db: Session,
    application_id: int,
    agent_name: str,
    task: str,
    fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Run one agent task and record it (status, output, errors) in agent_runs."""
    run = AgentRun(
        application_id=application_id,
        agent_name=agent_name,
        task=task,
        status="running",
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        output = fn()
        status, error = "completed", None
    except Exception as exc:
        db.rollback()
        output, status, error = {"error": str(exc)[:500]}, "failed", str(exc)[:1000]
    record = db.get(AgentRun, run_id)
    record.status = status
    record.output = output
    record.error = error
    record.finished_at = utcnow()
    db.commit()
    return output


def reset_investigation(db: Session, application_id: int) -> None:
    """Clear previous results so an investigation can be re-run from scratch."""
    for model in (Finding, Evidence, Claim, Assessment, Report, AgentRun):
        db.query(model).filter(model.application_id == application_id).delete(synchronize_session=False)
    db.commit()