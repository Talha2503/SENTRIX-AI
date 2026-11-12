"""Decision Intelligence agent: dimension scores (risk, coverage and confidence reported separately)
and the investigation report.

Principles: missing information lowers COVERAGE, never risk. Only observed contradictions or anomalies
add risk points. No overall score is given when coverage is too low. Weights are illustrative.
"""
import json
import re
from collections import Counter

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.llm import LLMError, call_json
from app.models.models import (
    AgentRun, Application, Assessment, Claim, Document, Evidence, Finding, Report,
)
from app.services.calculations import metric_by_period

AGENT = "decision_intelligence"
CALC_VERSION = "v1"
MIN_COVERAGE_FOR_OVERALL = 0.4

DIMENSIONS = {
    "financial_stability": {"label": "Financial stability", "weight": 0.30, "categories": ["financial"]},
    "environmental_performance": {"label": "Environmental performance", "weight": 0.30,
                                  "categories": ["greenwashing", "data_quality"]},
    "green_criteria_alignment": {"label": "Green-criteria alignment", "weight": 0.25, "categories": ["taxonomy"]},
    "climate_exposure": {"label": "Climate exposure", "weight": 0.15, "categories": ["climate"]},
}
SEVERITY_POINTS = {"high": 35, "medium": 20, "low": 8}
VERIFICATION_FACTOR = {"disputed": 0.5, "unsupported": 0.0}
RISK_STATUSES = {"contradictory", "potential_anomaly"}
OPEN_STATUSES = {"insufficient_information", "unverified", "not_assessed"}
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

BANNED_RE = re.compile(r"fraud|certif|guarantee|illegal|criminal|deceiv|\bliar|\blying", re.I)

NARRATIVE_SYSTEM = """You write the executive summary of a green-finance due-diligence report for human reviewers.
Rewrite the FACTS as a concise, plain-English summary of 4 to 6 sentences.
Rules: use only information in the FACTS; keep every number exactly as given; state uncertainty and what is missing; do not accuse anyone of fraud or misconduct; do not recommend approval or rejection; do not claim certification."""


class Narrative(BaseModel):
    summary: str


def risk_level(score: float | None) -> str:
    if score is None:
        return "not assessed"
    if score < 25:
        return "low"
    if score < 50:
        return "moderate"
    if score < 75:
        return "elevated"
    return "high"


def reliability(cov: float) -> str:
    return "adequate" if cov >= 0.75 else "partial" if cov >= 0.5 else "limited"


def latest_output(db: Session, application_id: int, agent_name: str) -> dict:
    run = db.scalars(
        select(AgentRun)
        .where(AgentRun.application_id == application_id, AgentRun.agent_name == agent_name,
               AgentRun.status == "completed")
        .order_by(AgentRun.id.desc())
    ).first()
    return (run.output or {}) if run else {}


# ------------------------------------------------------------------ coverage
def cov_financial(out: dict) -> float:
    return min(1.0, len(out.get("indicators", {})) / 7) if out.get("assessed") else 0.0


def cov_taxonomy(out: dict) -> float:
    outcomes = [o for reqs in (out.get("activities") or {}).values() for o in reqs.values()]
    applicable = [o for o in outcomes if o != "not_assessed"]
    return sum(1 for o in applicable if o == "met") / len(applicable) if applicable else 0.0


def cov_environmental(db: Session, application_id: int, claims: list[Claim]) -> float:
    quantified = [c for c in claims if c.category in ("emissions", "energy") and c.value is not None]
    checks = [
        len(metric_by_period(db, application_id, "electricity_kwh")) >= 2,
        len(metric_by_period(db, application_id, "production_tonnes")) >= 2,
    ]
    if quantified:
        checks.append(all(c.baseline_period for c in quantified))
    if any(c.category == "emissions" for c in quantified):
        has_method = db.scalar(
            select(func.count()).select_from(Evidence).where(
                Evidence.application_id == application_id, Evidence.metric == "methodology_statement")
        )
        checks.append(bool(has_method))
    return sum(checks) / len(checks)


# ------------------------------------------------------------------ risk
def risk_from_findings(findings: list[Finding]):
    total, basis = 0.0, []
    for f in findings:
        if f.status not in RISK_STATUSES:
            continue
        points = SEVERITY_POINTS.get(f.severity, 8) * VERIFICATION_FACTOR.get(f.verification_status, 1.0)
        if points > 0:
            total += points
            basis.append({"finding_id": f.id, "title": f.title, "points": round(points, 1),
                          "verification": f.verification_status})
    return min(100.0, total), basis


def climate_score(out: dict) -> float:
    bonus = {"elevated": 10, "moderate": 4}.get(out.get("transition_level"), 0)
    return min(100.0, 12 * out.get("elevated", 0) + 5 * out.get("moderate", 0) + bonus)


# ------------------------------------------------------------------ report pieces
def finding_entry(f: Finding) -> dict:
    return {
        "id": f.id, "title": f.title, "agent": f.agent_name, "category": f.category, "status": f.status,
        "severity": f.severity, "verification_status": f.verification_status,
        "confidence": f.confidence, "claim_id": f.claim_id,
        "recommended_followup": f.recommended_followup,
        "evidence_ids": [e.id for e in f.evidence_items],
    }


def template_summary(org, application, n_docs, findings, claims, overall) -> tuple[str, str]:
    supported = sum(1 for f in findings if f.status == "verified")
    flagged = sum(1 for f in findings if f.status in RISK_STATUSES)
    open_ = sum(1 for f in findings if f.status in OPEN_STATUSES)

    reasons = []
    for f in findings:
        if f.claim_id and f.status == "insufficient_information" and f.category == "greenwashing":
            claim = next((c for c in claims if c.id == f.claim_id), None)
            if claim is not None:
                reasons.append(f"The claim \"{claim.claim_text}\" is insufficiently supported by the submitted "
                               f"evidence ({f.title[0].lower() + f.title[1:]}).")
    if not reasons:
        top = [f for f in findings if f.status in RISK_STATUSES][:2]
        reasons = [f"Flagged for review: {f.title}." for f in top]
    headline = " ".join(reasons[:2])

    amount = application.requested_amount
    request = f"{application.currency} {amount:,.0f} " if amount else ""
    parts = [
        f"Preliminary review of {org.name} for a {request}green-financing request"
        + (f" ({application.project_description})." if application.project_description else "."),
        f"{n_docs} document(s) were analysed, producing {len(findings)} findings: {supported} supported by the "
        f"evidence, {flagged} flagged for review and {open_} open because information is missing or unverified.",
    ]
    if headline:
        parts.append(headline)
    if overall["risk_score"] is not None:
        parts.append(
            f"Indicative overall risk is {overall['risk_level']} ({overall['risk_score']:.0f}/100) with "
            f"{overall['coverage'] * 100:.0f}% evidence coverage ({overall['reliability']}) and should be read "
            "together with the unresolved items."
        )
    else:
        parts.append(
            f"An overall risk score is not given because evidence coverage is only "
            f"{overall['coverage'] * 100:.0f}% ({overall['reliability']})."
        )
    parts.append("This is decision support for human review, not an approval, rejection or certification.")
    facts = " ".join(parts)
    return facts, " ".join(f.title for f in findings[:12])


def polish_summary(facts: str, extra_text: str) -> tuple[str, str]:
    """Let the model rewrite the summary; keep it only if it adds no numbers and no accusatory wording."""
    try:
        result = call_json(NARRATIVE_SYSTEM, f"FACTS:\n{facts}", Narrative, max_tokens=900)
    except LLMError:
        return facts, "template"
    text = result.summary.strip()
    allowed = facts + " " + extra_text
    numbers = re.findall(r"\d+(?:[.,]\d+)*", text)
    if not text or BANNED_RE.search(text) or any(n.rstrip(".,") not in allowed for n in numbers):
        return facts, "template"
    return text, "llm"


# ------------------------------------------------------------------ entry point
def run(db: Session, application_id: int) -> dict:
    application = db.get(Application, application_id)
    org = application.organization
    findings = db.scalars(select(Finding).where(Finding.application_id == application_id).order_by(Finding.id)).all()
    claims = db.scalars(select(Claim).where(Claim.application_id == application_id).order_by(Claim.id)).all()
    docs = db.scalars(select(Document).where(Document.application_id == application_id)).all()
    processed = [d for d in docs if d.status == "processed"]

    fin_out = latest_output(db, application_id, "financial_intelligence")
    tax_out = latest_output(db, application_id, "green_taxonomy")
    clim_out = latest_output(db, application_id, "climate_risk")
    doc_out = latest_output(db, application_id, "document_intelligence")

    coverage = {
        "financial_stability": cov_financial(fin_out),
        "environmental_performance": cov_environmental(db, application_id, claims) if processed else 0.0,
        "green_criteria_alignment": cov_taxonomy(tax_out),
        "climate_exposure": float(clim_out.get("coverage", 0.0)),
    }

    dims = {}
    for key, spec in DIMENSIONS.items():
        dim_findings = [f for f in findings if f.category in spec["categories"]]
        cov = coverage[key]
        if cov <= 0:
            score, basis = None, []
        elif key == "climate_exposure":
            score = climate_score(clim_out)
            basis = [{"note": f"{clim_out.get('elevated', 0)} elevated and {clim_out.get('moderate', 0)} moderate "
                              f"physical hazard(s); transition exposure {clim_out.get('transition_level') or 'not assessed'}"}]
        else:
            score, basis = risk_from_findings(dim_findings)
        confs = [f.confidence for f in dim_findings if f.confidence is not None]
        dims[key] = {
            "label": spec["label"],
            "weight": spec["weight"],
            "risk_score": round(score, 1) if score is not None else None,
            "risk_level": risk_level(score),
            "coverage": round(cov, 2),
            "reliability": reliability(cov),
            "confidence": round(sum(confs) / len(confs), 2) if confs else None,
            "findings": len(dim_findings),
            "basis": basis,
        }

    overall_cov = sum(d["weight"] * d["coverage"] for d in dims.values())
    assessed = [d for d in dims.values() if d["risk_score"] is not None]
    overall_risk = overall_conf = None
    if assessed and overall_cov >= MIN_COVERAGE_FOR_OVERALL:
        wsum = sum(d["weight"] for d in assessed)
        overall_risk = sum(d["weight"] * d["risk_score"] for d in assessed) / wsum
        confs = [(d["weight"], d["confidence"]) for d in assessed if d["confidence"] is not None]
        if confs:
            overall_conf = sum(w * c for w, c in confs) / sum(w for w, _ in confs)
    overall = {
        "risk_score": round(overall_risk, 1) if overall_risk is not None else None,
        "risk_level": risk_level(overall_risk),
        "coverage": round(overall_cov, 2),
        "reliability": reliability(overall_cov),
        "confidence": round(overall_conf, 2) if overall_conf is not None else None,
    }

    facts, extra = template_summary(org, application, len(processed), findings, claims, overall)
    summary_text, summary_source = polish_summary(facts, extra) if findings else (facts, "template")

    ranked = sorted(findings, key=lambda f: (SEVERITY_RANK.get(f.severity, 3), f.id))
    supported = [finding_entry(f) for f in ranked if f.status == "verified"]
    issues = [finding_entry(f) for f in ranked if f.status in RISK_STATUSES]
    unresolved = [finding_entry(f) for f in ranked if f.status in OPEN_STATUSES]
    followups, seen = [], set()
    for f in ranked:
        if f.status != "verified" and f.recommended_followup and f.recommended_followup not in seen:
            seen.add(f.recommended_followup)
            followups.append(f.recommended_followup)

    limitations = [
        "Figures are extracted from submitted documents and have not been independently audited or verified.",
        "Green-criteria screening uses an illustrative prototype criteria set, not the official Pakistan Green Taxonomy.",
        "Climate screening is qualitative and based on a small illustrative reference, not hazard maps or projections.",
        "Dimension weights and risk thresholds are illustrative design assumptions, not regulatory or banking values.",
        "Missing information is shown as reduced coverage; it is not treated as poor performance or misconduct.",
    ]
    missing = sorted(set(["sustainability_report", "energy_records", "production_data", "financial_statement"])
                     - {d.doc_type for d in processed})
    if missing:
        limitations.append("Document types not submitted: " + ", ".join(missing) + ".")
    if doc_out.get("incomplete_periods"):
        limitations.append("Incomplete monthly records: " + "; ".join(doc_out["incomplete_periods"]) + ".")
    failed = [d.filename for d in docs if d.status == "failed"]
    if failed:
        limitations.append("Documents that could not be processed: " + ", ".join(failed) + ".")

    content = {
        "title": f"Green-finance investigation report: {org.name}",
        "application": {
            "id": application.id, "organization": org.name, "sector": org.sector, "location": org.location,
            "project": application.project_description, "requested_amount": application.requested_amount,
            "currency": application.currency,
        },
        "executive_summary": summary_text,
        "executive_summary_source": summary_source,
        "overall": overall,
        "dimensions": dims,
        "claims": [{"id": c.id, "text": c.claim_text, "category": c.category, "value": c.value, "unit": c.unit,
                    "baseline_period": c.baseline_period, "status": c.status, "page": c.page_number}
                   for c in claims],
        "supported_findings": supported,
        "issues_for_review": issues,
        "unresolved_questions": unresolved,
        "recommended_followups": followups,
        "finding_counts": dict(Counter(f.status for f in findings)),
        "verification_counts": dict(Counter(f.verification_status for f in findings)),
        "limitations": limitations,
        "disclaimers": [
            "SENTRIX AI is a decision-support tool. It does not approve or reject financing, certify environmental "
            "performance, or make legal findings of fraud or greenwashing.",
            "Final decisions remain with qualified professionals and authorised institutions.",
        ],
    }

    db.query(Assessment).filter(Assessment.application_id == application_id).delete(synchronize_session=False)
    db.query(Report).filter(Report.application_id == application_id).delete(synchronize_session=False)
    db.add(Assessment(
        application_id=application_id,
        calculation_version=CALC_VERSION,
        dimension_scores={"dimensions": dims, "overall": overall},
        coverage={"overall": round(overall_cov, 2), "by_dimension": {k: round(v, 2) for k, v in coverage.items()}},
        overall_confidence=overall["confidence"],
        limitations="\n".join(limitations),
    ))
    db.add(Report(application_id=application_id, summary=summary_text,
                  content=json.loads(json.dumps(content, default=str)), review_status="pending_review"))
    db.commit()
    return {"overall": overall, "summary_source": summary_source, "findings": len(findings)}