"""Greenwashing Detection agent: rule-based indicators, never accusations.

Every comparison uses deterministic code. Findings say what is documented, what is missing and
what does not line up, and always leave room for alternative explanations.
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Claim, Document, DocumentChunk, Evidence
from app.services.calculations import add_calc_evidence, metric_by_period, pct_change, two_latest
from app.services.findings import STATUS_PRIORITY, add_finding

AGENT = "greenwashing_detection"
TOLERANCE_POINTS = 5.0  # allowed gap (percentage points) between a claim and the records

METHOD_RE = re.compile(
    r"GHG Protocol|methodolog|ISO\s*14064|emission factor|\bScope\s*[123]\b|IPCC|calculation method", re.I
)
REF_RE = re.compile(r"\b[A-Z]{2,4}-\d{4}-\d{2,4}\b")
EFFICIENCY_RE = re.compile(r"energy[- ]efficien|efficiency", re.I)
IMPROVE_RE = re.compile(r"improv|increas|better|enhanc|reduc|lower|cut\b|fell|fall", re.I)
PER_UNIT_RE = re.compile(r"per tonne|per unit|intensity|efficien", re.I)

ALTERNATIVES = (
    "Possible explanations that the verification step must test: a change in energy source or grid factor, "
    "a different reporting boundary or baseline year, product mix, or an error in either document."
)


class Run:
    def __init__(self, db: Session, application_id: int):
        self.db = db
        self.app_id = application_id
        self.claim_status: dict[int, list[str]] = {}
        self.findings = 0

    def add(self, *, claim=None, **kwargs):
        finding = add_finding(
            self.db, self.app_id, AGENT, "greenwashing",
            claim_id=claim.id if claim is not None else None, **kwargs,
        )
        if claim is not None:
            self.claim_status.setdefault(claim.id, []).append(kwargs.get("status", "unverified"))
        self.findings += 1
        return finding


def source_evidence(db: Session, claim_ids: list[int]) -> list[Evidence]:
    if not claim_ids:
        return []
    return db.scalars(
        select(Evidence).where(Evidence.claim_id.in_(claim_ids), Evidence.evidence_type == "claim_source")
    ).all()


def compute_calcs(db: Session, application_id: int) -> dict:
    calc: dict = {}
    elec = metric_by_period(db, application_id, "electricity_kwh")
    prod = metric_by_period(db, application_id, "production_tonnes")
    pair = two_latest(elec)
    if not pair:
        return calc
    base, cmp_ = pair
    period = f"{base}->{cmp_}"
    e0, e1 = elec[base], elec[cmp_]
    change = pct_change(e0.value, e1.value)
    if change is not None:
        ev = add_calc_evidence(
            db, application_id, "electricity_change_pct", round(change, 2), "%", period,
            f"electricity_kwh {base} {e0.value:,.0f} -> {cmp_} {e1.value:,.0f} = {change:+.1f}%",
        )
        calc["electricity_change_pct"] = (change, ev, [e0, e1])
    if base in prod and cmp_ in prod:
        p0, p1 = prod[base], prod[cmp_]
        pchange = pct_change(p0.value, p1.value)
        if pchange is not None:
            ev = add_calc_evidence(
                db, application_id, "production_change_pct", round(pchange, 2), "%", period,
                f"production_tonnes {base} {p0.value:,.0f} -> {cmp_} {p1.value:,.0f} = {pchange:+.1f}%",
            )
            calc["production_change_pct"] = (pchange, ev, [p0, p1])
        if p0.value and p1.value:
            i0, i1 = e0.value / p0.value, e1.value / p1.value
            ichange = pct_change(i0, i1)
            if ichange is not None:
                ev = add_calc_evidence(
                    db, application_id, "kwh_per_tonne_change_pct", round(ichange, 2), "%", period,
                    f"kWh per tonne {base} {i0:,.1f} -> {cmp_} {i1:,.1f} = {ichange:+.1f}%",
                )
                calc["kwh_per_tonne_change_pct"] = (ichange, ev, [e0, e1, p0, p1])
    return calc


def find_methodology(db: Session, application_id: int, chunk_rows) -> dict:
    for row in chunk_rows:
        match = METHOD_RE.search(row.text)
        if match:
            start = max(0, match.start() - 100)
            snippet = row.text[start: match.end() + 140].replace("\n", " ")
            ev = Evidence(
                application_id=application_id,
                document_id=row.doc_id,
                chunk_id=row.id,
                page_number=row.page_number,
                excerpt=snippet[:500],
                evidence_type="supporting",
                metric="methodology_statement",
                extraction_method="keyword_search",
            )
            db.add(ev)
            db.flush()
            return {"found": True, "evidence": ev, "term": match.group(0)}
    return {"found": False, "evidence": None, "term": None}


# ------------------------------------------------------------------ individual checks
def check_emissions_claim(r: Run, claim: Claim, calc: dict, method: dict):
    src = source_evidence(r.db, [claim.id])
    gaps = []
    if not claim.baseline_period:
        gaps.append("no baseline year is stated")
    if not method["found"]:
        gaps.append("no calculation methodology or reporting boundary is described in the submitted documents")

    if gaps:
        r.add(
            claim=claim,
            title=f"Emissions claim ({claim.value:+g}%) lacks a documented baseline and/or method",
            explanation=(
                f"The claim \"{claim.claim_text}\" (page {claim.page_number}) cannot be assessed as stated: "
                + "; ".join(gaps) + ". This is a documentation gap, not evidence of wrongdoing. "
                "The claim stays unverified until a baseline and calculation method are provided."
            ),
            severity="high" if abs(claim.value) >= 20 else "medium",
            status="insufficient_information",
            confidence=0.8,
            confidence_notes="Absence was established by searching all submitted document text; "
                             "documents that were not submitted cannot be searched.",
            followup="Ask for the baseline year, the emissions inventory or calculation (for example GHG Protocol), "
                     "the reporting boundary and the emission factors used.",
            evidence=src + ([method["evidence"]] if method["found"] else []),
        )
    else:
        r.add(
            claim=claim,
            title="Emissions claim documents its baseline and method",
            explanation=(
                f"The claim \"{claim.claim_text}\" states a baseline ({claim.baseline_period}) and the submitted "
                f"documents describe a methodology (found: \"{method['term']}\"). Documentation exists; the figures "
                "are checked separately against the records."
            ),
            severity="low", status="verified", confidence=0.7,
            confidence_notes="Keyword search of submitted documents; the method itself is not audited.",
            evidence=src + [method["evidence"]],
        )

    el = calc.get("electricity_change_pct")
    if el is None:
        r.add(
            claim=claim,
            title="Emissions claim cannot be cross-checked: no electricity records",
            explanation="No electricity records covering two periods were found, so the claimed change cannot be "
                        "compared with consumption data.",
            severity="medium", status="insufficient_information",
            followup="Request monthly electricity bills or meter records for the baseline and reporting years.",
            evidence=src,
        )
        return
    change, ev_calc, inputs = el
    extra = ""
    related = []
    if "production_change_pct" in calc:
        extra += f" Production changed {calc['production_change_pct'][0]:+.1f}%."
        related += [calc["production_change_pct"][1]] + calc["production_change_pct"][2]
    if "kwh_per_tonne_change_pct" in calc:
        extra += f" Electricity per tonne produced changed {calc['kwh_per_tonne_change_pct'][0]:+.1f}%."
        related += [calc["kwh_per_tonne_change_pct"][1]]
    evidence = src + [ev_calc] + inputs + related

    if change <= claim.value + TOLERANCE_POINTS:
        r.add(
            claim=claim,
            title="Claimed emissions change is consistent with the electricity records",
            explanation=(
                f"The company claims {claim.value:+g}%. Electricity consumption in the records changed "
                f"{change:+.1f}% ({ev_calc.reporting_period}).{extra} Electricity is a proxy for location-based "
                "Scope 2 emissions only."
            ),
            severity="low", status="verified", confidence=0.7,
            confidence_notes="Electricity records are a partial proxy for total emissions.",
            evidence=evidence,
        )
    else:
        r.add(
            claim=claim,
            title="Claimed emissions reduction is not corroborated by the electricity records",
            explanation=(
                f"The company claims {claim.value:+g}%. Electricity consumption in the submitted records changed "
                f"{change:+.1f}% ({ev_calc.reporting_period}).{extra} Electricity is only one emissions source, "
                f"so this does not prove that emissions rose. {ALTERNATIVES}"
            ),
            severity="high" if (change > 0 and claim.value <= -10) else "medium",
            status="potential_anomaly",
            confidence=0.7,
            confidence_notes="Based on a deterministic comparison; electricity is a partial proxy for total emissions.",
            followup="Ask the applicant to reconcile the claim with the electricity records and state the energy "
                     "sources and boundary used.",
            evidence=evidence,
        )


def check_efficiency_claim(r: Run, claim: Claim, calc: dict):
    text = claim.claim_text
    numeric = claim.value is not None
    if not ((numeric and claim.value < 0) or IMPROVE_RE.search(text)):
        return
    src = source_evidence(r.db, [claim.id])
    per_unit = bool(PER_UNIT_RE.search(text))
    if per_unit and "kwh_per_tonne_change_pct" in calc:
        key, label = "kwh_per_tonne_change_pct", "electricity per tonne produced"
    elif "electricity_change_pct" in calc:
        key, label = "electricity_change_pct", "total electricity consumption"
    else:
        r.add(
            claim=claim,
            title="Energy-efficiency claim cannot be checked: records are missing",
            explanation=f"The claim \"{text}\" cannot be compared with records because no electricity (and "
                        "production) records covering two periods were found.",
            severity="medium", status="insufficient_information",
            followup="Request electricity and production records for the baseline and reporting years.",
            evidence=src,
        )
        return
    actual, ev_calc, inputs = calc[key]
    ok = (actual <= claim.value + TOLERANCE_POINTS) if numeric else (actual < 0)
    note = "" if numeric else " The claim is not quantified, which limits how far it can be verified."
    if ok:
        r.add(
            claim=claim,
            title="Energy-efficiency claim is consistent with the records",
            explanation=f"The claim \"{text}\" is consistent with the records: {label} changed "
                        f"{actual:+.1f}% ({ev_calc.reporting_period}).{note}",
            severity="low", status="verified", confidence=0.7,
            confidence_notes="Deterministic comparison against the submitted records.",
            evidence=src + [ev_calc] + inputs,
        )
    else:
        r.add(
            claim=claim,
            title="Energy-efficiency claim is not reflected in the records",
            explanation=(
                f"The claim \"{text}\" implies an improvement, but {label} changed {actual:+.1f}% "
                f"({ev_calc.reporting_period}) in the submitted records.{note} {ALTERNATIVES}"
            ),
            severity="high" if actual > 10 else "medium",
            status="contradictory", confidence=0.75,
            confidence_notes="Deterministic comparison against the submitted records.",
            followup="Ask the applicant to explain the difference between the claim and the records.",
            evidence=src + [ev_calc] + inputs,
        )


def check_practice_claims(r: Run, claims: list[Claim], chunk_text: dict[int, str]):
    referenced, unreferenced = [], []
    for claim in claims:
        text = chunk_text.get(claim.chunk_id, "")
        if REF_RE.search(text) or "appendix" in text.lower():
            referenced.append(claim)
        else:
            unreferenced.append(claim)
    for claim in claims:
        r.claim_status.setdefault(claim.id, []).append("unverified")

    if unreferenced:
        listing = "\n".join(f"- {c.claim_text} (page {c.page_number})" for c in unreferenced)
        r.add(
            title=f"{len(unreferenced)} practice claim(s) have no supporting records referenced or attached",
            explanation=(
                "These operational claims are stated without any reference to supporting records "
                f"(invoices, certificates, work orders, logs):\n{listing}\n\nThis does not mean the practices "
                "do not exist; they are unverified."
            ),
            severity="medium", status="unverified", confidence=0.8,
            confidence_notes="No record reference was found next to these claims or in the submitted documents.",
            followup="Request the records that evidence each practice.",
            evidence=source_evidence(r.db, [c.id for c in unreferenced]),
        )
    if referenced:
        listing = "\n".join(f"- {c.claim_text} (page {c.page_number})" for c in referenced)
        r.add(
            title=f"{len(referenced)} practice claim(s) reference records that were not attached",
            explanation=(
                "These claims point to supporting records (for example an appendix of work orders or "
                f"certificates), but copies of those records were not among the uploaded documents:\n{listing}"
            ),
            severity="low", status="unverified", confidence=0.7,
            confidence_notes="References were detected by pattern; the referenced documents were not provided.",
            followup="Obtain copies of the referenced records.",
            evidence=source_evidence(r.db, [c.id for c in referenced]),
        )


def check_consistency(r: Run, filenames: dict[int, str]):
    rows = r.db.scalars(
        select(Evidence).where(
            Evidence.application_id == r.app_id,
            Evidence.evidence_type == "contextual",
            Evidence.metric.is_not(None),
            Evidence.value.is_not(None),
            Evidence.reporting_period.is_not(None),
            Evidence.extraction_method.in_(["csv_sum", "table_parser"]),
        )
    ).all()
    groups: dict[tuple, list[Evidence]] = {}
    for e in rows:
        groups.setdefault((e.metric, e.reporting_period), []).append(e)

    compared, mismatched, compared_evidence = 0, 0, []
    for (metric, period), items in groups.items():
        if len({e.document_id for e in items}) < 2:
            continue
        compared += 1
        compared_evidence += items
        values = [e.value for e in items]
        spread = (max(values) - min(values)) / max(abs(max(values)), 1e-9) * 100
        if spread > 1.0:
            mismatched += 1
            detail = "; ".join(f"{filenames.get(e.document_id, 'document')}: {e.value:,.1f}" for e in items)
            r.add(
                title=f"Reported {metric} for {period} differs between documents ({spread:.1f}% apart)",
                explanation=f"The same figure is reported differently: {detail}. {ALTERNATIVES}",
                severity="high" if spread > 10 else "medium", status="contradictory", confidence=0.85,
                confidence_notes="Deterministic comparison of figures extracted from different documents.",
                followup="Ask the applicant which figure is correct and why the documents differ.",
                evidence=items,
            )
    if compared and not mismatched:
        r.add(
            title="Figures reported in the statement match the underlying records",
            explanation=f"{compared} figure(s) reported in more than one document were compared and agree "
                        "within 1%.",
            severity="low", status="verified", confidence=0.85,
            confidence_notes="Deterministic comparison of figures extracted from different documents.",
            evidence=compared_evidence,
        )


# ------------------------------------------------------------------ entry point
def run(db: Session, application_id: int) -> dict:
    r = Run(db, application_id)
    claims = db.scalars(select(Claim).where(Claim.application_id == application_id).order_by(Claim.id)).all()
    chunk_rows = db.execute(
        select(
            DocumentChunk.id, DocumentChunk.text, DocumentChunk.page_number,
            Document.id.label("doc_id"), Document.filename,
        )
        .select_from(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.application_id == application_id)
        .order_by(Document.id, DocumentChunk.chunk_index)
    ).all()
    chunk_text = {row.id: row.text for row in chunk_rows}
    filenames = {row.doc_id: row.filename for row in chunk_rows}

    if not claims:
        r.add(
            title="No environmental claims were extracted from the submitted documents",
            explanation="No claims could be extracted, so greenwashing indicators were not assessed. Either the "
                        "documents contain no sustainability claims or text extraction failed.",
            severity="medium", status="insufficient_information",
            followup="Check the uploaded documents (scanned documents need OCR) and re-run.",
        )

    calc = compute_calcs(db, application_id)
    emissions = [c for c in claims if c.category == "emissions" and c.value is not None]
    method = find_methodology(db, application_id, chunk_rows) if emissions else {"found": False, "evidence": None}

    for claim in emissions:
        check_emissions_claim(r, claim, calc, method)
    for claim in claims:
        if claim.category == "projection" or claim in emissions:
            continue
        if claim.category == "energy" or EFFICIENCY_RE.search(claim.claim_text):
            check_efficiency_claim(r, claim, calc)
    practice = [c for c in claims if c.category == "practice"]
    if practice:
        check_practice_claims(r, practice, chunk_text)
    check_consistency(r, filenames)

    for claim in claims:
        statuses = r.claim_status.get(claim.id)
        if statuses:
            claim.status = max(statuses, key=lambda s: STATUS_PRIORITY.get(s, 0))
    db.commit()
    return {
        "claims_checked": len(claims),
        "findings": r.findings,
        "calculations": {k: round(v[0], 2) for k, v in calc.items()},
        "methodology_found": method["found"],
    }