"""Green Taxonomy agent: rule-based screening against an explicit criteria set (no LLM)."""
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.criteria import ACTIVITIES, CRITERIA_SET, EXCLUSION_PATTERNS, REQUIREMENTS
from app.models.models import Application, Claim, Document, DocumentChunk
from app.services.calculations import metric_by_period
from app.services.findings import add_finding

AGENT = "green_taxonomy"
OUTCOME_LABEL = {
    "met": "MET",
    "unclear": "UNCLEAR (no evidence either way in the submitted documents)",
    "not_met": "NOT MET",
    "not_assessed": "NOT ASSESSED",
}
DISCHARGE_RE = re.compile(r"NEQS|discharge standard|effluent standard|discharge limit", re.I)
TREATMENT_CAPACITY_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:m3|m³|cubic met|kld|litres?|liters?|gallons?)", re.I)


@dataclass
class Ctx:
    db: Session
    application_id: int
    project_text: str
    claims: list
    chunk_texts: list


def check_capacity_stated(ctx: Ctx):
    match = re.search(r"\d+(?:\.\d+)?\s*(?:MWp?|kWp?)\b", ctx.project_text, re.I)
    if match:
        return "met", f"Installed capacity is stated in the project description ({match.group(0)}).", []
    return "unclear", "No installed capacity (kW or MW) is stated in the project description.", []


def _metric_check(ctx: Ctx, metric: str, label: str):
    by = metric_by_period(ctx.db, ctx.application_id, metric)
    if len(by) >= 2:
        periods = sorted(by)
        return "met", f"{label} found for {', '.join(periods)}.", [by[p] for p in periods]
    return "unclear", f"{label} for at least two periods were not found in the submitted documents.", []


def check_baseline_energy_data(ctx: Ctx):
    return _metric_check(ctx, "electricity_kwh", "Electricity consumption records")


def check_production_data(ctx: Ctx):
    return _metric_check(ctx, "production_tonnes", "Production records")


def check_claims_have_baseline(ctx: Ctx):
    numeric = [c for c in ctx.claims if c.category in ("emissions", "energy") and c.value is not None]
    if not numeric:
        return "not_assessed", "No quantified emissions or energy performance claims were extracted.", []
    missing = [c for c in numeric if not c.baseline_period]
    if not missing:
        return "met", "Every quantified performance claim states a baseline period.", []
    return "unclear", f"{len(missing)} of {len(numeric)} quantified performance claim(s) state no baseline period.", []


def check_treatment_capacity(ctx: Ctx):
    match = TREATMENT_CAPACITY_RE.search(ctx.project_text)
    if match:
        return "met", f"Treatment capacity is stated ({match.group(0)}).", []
    return "unclear", "No treatment capacity is stated in the project description.", []


def check_discharge_standard(ctx: Ctx):
    for _chunk_id, text in ctx.chunk_texts:
        if DISCHARGE_RE.search(text):
            return "met", "A discharge standard is referenced in the submitted documents.", []
    return "unclear", "No discharge standard is referenced in the submitted documents.", []


CHECKS = {
    "capacity_stated": check_capacity_stated,
    "baseline_energy_data": check_baseline_energy_data,
    "production_data": check_production_data,
    "claims_have_baseline": check_claims_have_baseline,
    "treatment_capacity_stated": check_treatment_capacity,
    "discharge_standard_stated": check_discharge_standard,
}


def run(db: Session, application_id: int) -> dict:
    application = db.get(Application, application_id)
    claims = db.scalars(select(Claim).where(Claim.application_id == application_id)).all()
    chunk_texts = [
        (r.id, r.text)
        for r in db.execute(
            select(DocumentChunk.id, DocumentChunk.text)
            .select_from(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.application_id == application_id)
        ).all()
    ]
    project_text = (application.project_description or "").strip()
    meta = {"criteria_set": CRITERIA_SET["name"], "version": CRITERIA_SET["version"]}
    header = (
        f"Criteria set: {CRITERIA_SET['name']} v{CRITERIA_SET['version']}. {CRITERIA_SET['source']}"
    )

    if not project_text:
        add_finding(
            db, application_id, AGENT, "taxonomy",
            "Green criteria could not be assessed: no project description",
            f"{header}\n\nThe application has no project description to map to the criteria.",
            severity="medium", status="not_assessed",
            followup="Provide a description of the financed project and its activities.",
        )
        db.commit()
        return {**meta, "assessed": False}

    ctx = Ctx(db, application_id, project_text, claims, chunk_texts)

    excluded = [p for p in EXCLUSION_PATTERNS if re.search(p, project_text, re.I)]
    if excluded:
        add_finding(
            db, application_id, AGENT, "taxonomy",
            "Project description mentions an activity the criteria treat as excluded",
            f"{header}\n\nThe project description matches an exclusion pattern. This needs human review; "
            "wording alone does not establish that the project is ineligible.",
            severity="high", status="potential_anomaly", confidence=0.6,
            confidence_notes="Keyword match on the project description only.",
            followup="Clarify the role of the mentioned activity in the project.",
        )

    matched = [a for a in ACTIVITIES if any(re.search(p, project_text, re.I) for p in a["patterns"])]
    if not matched:
        add_finding(
            db, application_id, AGENT, "taxonomy",
            "Project could not be mapped to the available criteria",
            f"{header}\n\nNo activity in the criteria set matched the project description.",
            severity="low", status="not_assessed",
            followup="Provide a more detailed project description, or extend the criteria set.",
        )
        db.commit()
        return {**meta, "assessed": False, "matched": []}

    summary = {}
    for activity in matched:
        outcomes = []
        for req in activity["requirements"]:
            outcome, note, evidence = CHECKS[req](ctx)
            outcomes.append((req, outcome, note, evidence))

        applicable = [o for o in outcomes if o[1] != "not_assessed"]
        met = [o for o in applicable if o[1] == "met"]
        unclear = [o for o in applicable if o[1] == "unclear"]
        if not applicable:
            status = "not_assessed"
        elif len(met) == len(applicable):
            status = "verified"
        else:
            status = "insufficient_information"
        severity = "low" if status in ("verified", "not_assessed") else ("medium" if len(unclear) >= 2 else "low")

        lines = [
            f"- {REQUIREMENTS[req]['label']}: {OUTCOME_LABEL[outcome]}. {note}"
            for req, outcome, note, _ in outcomes
        ]
        explanation = (
            f"{header}\n\nActivity: {activity['name']} ({activity['id']}); objective: {activity['objective']}.\n"
            f"Project description: \"{project_text}\"\n\nRequirement checks:\n" + "\n".join(lines)
            + "\n\nThis is a screening result for human review, not an eligibility determination."
        )
        followup = None
        if unclear:
            asks = "; ".join(REQUIREMENTS[req]["ask"] for req, _, _, _ in unclear)
            followup = f"Ask the applicant to: {asks}."
        evidence_all = [e for _, _, _, ev in outcomes for e in ev]

        add_finding(
            db, application_id, AGENT, "taxonomy",
            f"{activity['name']}: {len(met)} of {len(applicable)} requirements evidenced",
            explanation,
            severity=severity, status=status,
            confidence=round(len(met) / len(applicable), 2) if applicable else None,
            confidence_notes="Share of requirements for which evidence was found in the submitted documents.",
            followup=followup, evidence=evidence_all,
        )
        summary[activity["id"]] = {req: outcome for req, outcome, _, _ in outcomes}

    db.commit()
    return {**meta, "assessed": True, "activities": summary, "excluded_patterns": excluded}