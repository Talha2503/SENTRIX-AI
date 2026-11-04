"""Shared helper for recording findings together with their evidence links."""
from sqlalchemy.orm import Session

from app.models.models import Finding

# Higher number = more serious. Used to roll finding statuses up to a claim.
STATUS_PRIORITY = {
    "contradictory": 5,
    "potential_anomaly": 4,
    "insufficient_information": 3,
    "unverified": 2,
    "verified": 1,
    "not_assessed": 0,
}


def add_finding(
    db: Session,
    application_id: int,
    agent_name: str,
    category: str,
    title: str,
    explanation: str,
    *,
    severity: str = "medium",
    status: str = "unverified",
    confidence: float | None = None,
    confidence_notes: str | None = None,
    followup: str | None = None,
    claim_id: int | None = None,
    evidence=(),
) -> Finding:
    unique = {e.id: e for e in evidence if e is not None}
    finding = Finding(
        application_id=application_id,
        claim_id=claim_id,
        agent_name=agent_name,
        category=category,
        title=title[:255],
        explanation=explanation,
        severity=severity,
        status=status,
        verification_status="pending",
        confidence=confidence,
        confidence_notes=confidence_notes,
        recommended_followup=followup,
    )
    finding.evidence_items = list(unique.values())
    db.add(finding)
    db.flush()
    return finding