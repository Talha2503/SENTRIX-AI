"""Climate Risk agent: limited qualitative screening from location and sector (no LLM)."""
import re

from sqlalchemy.orm import Session

from app.core.climate_reference import (
    DEFAULT_REGION,
    DEFAULT_TRANSITION,
    REFERENCE,
    REGIONS,
    TRANSITION_RULES,
)
from app.models.models import Application, Evidence
from app.services.findings import add_finding

AGENT = "climate_risk"
LIMITS = (
    f"Reference: {REFERENCE['name']} v{REFERENCE['version']}. {REFERENCE['note']} "
    "Levels are screening judgements, not measurements or forecasts."
)


def match_region(location: str) -> dict:
    text = location.lower()
    for region in REGIONS:
        if any(key in text for key in region["keys"]):
            return region
    return DEFAULT_REGION


def match_transition(sector: str) -> dict:
    for rule in TRANSITION_RULES:
        if any(re.search(p, sector, re.I) for p in rule["patterns"]):
            return rule
    return DEFAULT_TRANSITION


def run(db: Session, application_id: int) -> dict:
    application = db.get(Application, application_id)
    org = application.organization
    location = (org.location or "").strip()
    sector = (org.sector or "").strip()

    profile = Evidence(
        application_id=application_id,
        excerpt=(f"Organization profile: sector={sector or 'not stated'}; "
                 f"location={location or 'not stated'}; country={org.country}"),
        evidence_type="contextual",
        metric="organization_profile",
        extraction_method="application_form",
    )
    db.add(profile)
    db.flush()

    coverage = (0.5 if location else 0.0) + (0.5 if sector else 0.0)
    elevated = moderate = 0
    region_name = None
    transition_level = None

    if location:
        region = match_region(location)
        region_name = region["name"]
        hazards = region["hazards"]
        elevated = sum(1 for _, level, _ in hazards if level == "elevated")
        moderate = sum(1 for _, level, _ in hazards if level == "moderate")
        lines = "\n".join(f"- {name}: {level}. {note}" for name, level, note in hazards)
        add_finding(
            db, application_id, AGENT, "climate",
            f"Physical climate exposure screening ({region_name}): {elevated} elevated, {moderate} moderate",
            f"Location stated: \"{location}\". Screening region: {region_name}.\n{lines}\n\n{LIMITS}",
            severity="medium" if elevated >= 2 else "low",
            status="verified", confidence=0.5,
            confidence_notes="Qualitative regional screening; not site-specific.",
            followup="For elevated hazards, obtain a site-specific hazard assessment and business-continuity plans.",
            evidence=[profile],
        )
    else:
        add_finding(
            db, application_id, AGENT, "climate",
            "Physical climate exposure not assessed: no location stated",
            "The application gives no plant location, so physical hazards cannot be screened. "
            "This is a data gap, not a negative finding.",
            severity="medium", status="insufficient_information",
            followup="Provide the address of the plant or financed asset.", evidence=[profile],
        )

    if sector:
        rule = match_transition(sector)
        transition_level = rule["level"]
        add_finding(
            db, application_id, AGENT, "climate",
            f"Transition risk screening ({sector}): {transition_level} exposure",
            f"Sector stated: \"{sector}\". {rule['why']}\n\n{LIMITS}",
            severity="low", status="verified", confidence=0.5,
            confidence_notes="Qualitative sector screening; not company-specific.",
            followup="Ask how the company manages energy price and buyer-requirement risk.",
            evidence=[profile],
        )
    else:
        add_finding(
            db, application_id, AGENT, "climate",
            "Transition risk not assessed: no sector stated",
            "The application gives no sector, so transition exposure cannot be screened.",
            severity="low", status="insufficient_information",
            followup="Provide the business sector.", evidence=[profile],
        )

    db.commit()
    return {
        "assessed": coverage > 0,
        "region": region_name,
        "elevated": elevated,
        "moderate": moderate,
        "transition_level": transition_level,
        "coverage": coverage,
        "reference_version": REFERENCE["version"],
    }