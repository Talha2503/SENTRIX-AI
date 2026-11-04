"""Deterministic helpers: all arithmetic happens here, never in the language model."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Evidence

# When the same figure exists in several documents, prefer primary records over company summaries.
SOURCE_PRIORITY = {"csv_sum": 0, "table_parser": 1}


def pct_change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return (new - old) / abs(old) * 100.0


def metric_by_period(db: Session, application_id: int, metric: str) -> dict[str, Evidence]:
    rows = db.scalars(
        select(Evidence)
        .where(
            Evidence.application_id == application_id,
            Evidence.metric == metric,
            Evidence.evidence_type == "contextual",
            Evidence.value.is_not(None),
            Evidence.reporting_period.is_not(None),
        )
        .order_by(Evidence.id)
    ).all()
    best: dict[str, Evidence] = {}
    for row in rows:
        current = best.get(row.reporting_period)
        if current is None or SOURCE_PRIORITY.get(row.extraction_method, 9) < SOURCE_PRIORITY.get(
            current.extraction_method, 9
        ):
            best[row.reporting_period] = row
    return best


def two_latest(by_period: dict) -> tuple[str, str] | None:
    periods = sorted(by_period)
    return (periods[-2], periods[-1]) if len(periods) >= 2 else None


def add_calc_evidence(
    db: Session,
    application_id: int,
    metric: str,
    value: float,
    unit: str | None,
    period: str,
    excerpt: str,
) -> Evidence:
    evidence = Evidence(
        application_id=application_id,
        excerpt=excerpt[:500],
        evidence_type="calculation",
        metric=metric,
        value=value,
        unit=unit,
        reporting_period=period,
        extraction_method="deterministic",
    )
    db.add(evidence)
    db.flush()
    return evidence