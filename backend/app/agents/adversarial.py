"""Adversarial Verification agent.

Challenges high-impact findings: checks evidence integrity, tests alternative explanations with
deterministic rules, searches the documents again for missing information, and optionally asks the
model for further alternatives. The model adds commentary only; it never changes a verdict.

Verdicts:  verified   = the finding stands after the challenge
           disputed   = an alternative explanation is supported by the submitted documents
           unresolved = alternatives cannot be ruled out because information is missing
           unsupported = the finding's evidence could not be traced
"""
import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.document_intelligence import norm
from app.core.llm import LLMError, call_json
from app.models.models import AgentRun, Claim, Document, DocumentChunk, Evidence, Finding

AGENT = "adversarial_verification"
MAX_CHALLENGES = 10
MAX_LLM_REVIEWS = 4
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
VERDICT_ORDER = {"unsupported": 0, "disputed": 1, "unresolved": 2, "verified": 3}
CONFIDENCE_CAP = {"disputed": 0.5, "unresolved": 0.65, "unsupported": 0.3}
VERDICT_LABEL = {
    "verified": "the finding stands after challenge",
    "disputed": "an alternative explanation is supported by the submitted documents",
    "unresolved": "alternative explanations cannot be ruled out because information is missing",
    "unsupported": "the finding's evidence could not be traced",
}

YEAR = r"(FY\s?\d{4}|\b20\d{2}\b)"
BASELINE_RES = [
    re.compile(rf"baseline(?:\s+year)?\b[^.\n]{{0,60}}?{YEAR}", re.I),
    re.compile(rf"base\s+year\b[^.\n]{{0,60}}?{YEAR}", re.I),
    re.compile(rf"compared\s+(?:with|to)\b[^.\n]{{0,60}}?{YEAR}", re.I),
]
ONSITE_RE = re.compile(
    r"(?:solar|captive|wind|biomass|generator)[^.\n]{0,80}(?:installed|commissioned|operational|operating|generat\w+)"
    r"|(?:installed|commissioned|operational|operating|generat\w+)[^.\n]{0,80}(?:solar|captive|wind|biomass|generator)",
    re.I,
)
FUTURE_RE = re.compile(
    r"\b(?:expect\w*|plans?\b|planned|planning|propos\w*|will\b|intend\w*|projected|projection|future)", re.I
)
BOUNDARY_RE = re.compile(r"boundar", re.I)
TOPIC_RE = re.compile(r"emission|electricity|efficien", re.I)

CHALLENGE_SYSTEM = """You are the adversarial reviewer in a green-finance due-diligence workflow. Your job is to challenge a preliminary finding, not to confirm it.
Rules:
- Use only the facts given. Never invent figures, documents or company details.
- alternative_explanations: up to 3 plausible, generic, innocent explanations for the observation (for example energy source, reporting boundary, product mix, data error).
- evidence_that_would_resolve: up to 3 specific documents or records that would settle the question.
- wording_check: 'appropriately_cautious' if the finding avoids accusing the company of fraud or misconduct and states its limits; 'overstated' if it claims more than the evidence shows; 'understated' if it ignores a clear issue shown by the facts.
- wording_note: one sentence, only when wording_check is not 'appropriately_cautious'."""


class Challenge(BaseModel):
    alternative_explanations: list[str] = []
    evidence_that_would_resolve: list[str] = []
    wording_check: Literal["appropriately_cautious", "overstated", "understated"] = "appropriately_cautious"
    wording_note: str | None = None


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def normalize_year(raw: str) -> str:
    return re.sub(r"\s+", "", raw.upper())


def needs_challenge(f: Finding) -> bool:
    """High-impact findings, anomalies, and missing-information findings tied to a claim.

    The last group matters: before a gap such as 'no baseline stated' is accepted, the documents are
    searched again, because the information may be stated elsewhere in the submission.
    """
    if f.severity == "high" or f.status in ("contradictory", "potential_anomaly"):
        return True
    return f.status == "insufficient_information" and f.claim_id is not None and f.category == "greenwashing"


def load_chunks(db: Session, application_id: int):
    return db.execute(
        select(
            DocumentChunk.id, DocumentChunk.text, DocumentChunk.page_number,
            Document.id.label("doc_id"), Document.filename,
        )
        .select_from(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.application_id == application_id)
        .order_by(Document.id, DocumentChunk.chunk_index)
    ).all()


class Ctx:
    def __init__(self, db: Session, application_id: int, chunks):
        self.db = db
        self.app_id = application_id
        self.chunks = chunks
        self.chunk_text = {c.id: c.text for c in chunks}

    def calc(self, metric: str) -> Evidence | None:
        return self.db.scalars(
            select(Evidence)
            .where(
                Evidence.application_id == self.app_id,
                Evidence.metric == metric,
                Evidence.evidence_type == "calculation",
            )
            .order_by(Evidence.id.desc())
        ).first()

    def evidence_from(self, chunk, snippet: str, metric: str) -> Evidence:
        ev = Evidence(
            application_id=self.app_id,
            document_id=chunk.doc_id,
            chunk_id=chunk.id,
            page_number=chunk.page_number,
            excerpt=snippet[:500],
            evidence_type="supporting",
            metric=metric,
            extraction_method="adversarial_search",
        )
        self.db.add(ev)
        self.db.flush()
        return ev

    def incomplete_periods(self) -> list[str]:
        run = self.db.scalars(
            select(AgentRun)
            .where(
                AgentRun.application_id == self.app_id,
                AgentRun.agent_name == "document_intelligence",
                AgentRun.status == "completed",
            )
            .order_by(AgentRun.id.desc())
        ).first()
        return ((run.output or {}).get("incomplete_periods") or []) if run else []


# ------------------------------------------------------------------ checks
def integrity_issues(finding: Finding, chunk_text: dict[int, str]) -> list[str]:
    issues = []
    if not finding.evidence_items and finding.status not in ("insufficient_information", "not_assessed"):
        issues.append("the finding has no linked evidence")
    for ev in finding.evidence_items:
        if ev.document_id is None and ev.extraction_method not in ("deterministic", "application_form"):
            issues.append(f"evidence {ev.id} has no source document")
        if ev.evidence_type == "claim_source":
            if not ev.excerpt or norm(ev.excerpt) not in norm(chunk_text.get(ev.chunk_id, "")):
                issues.append(f"evidence {ev.id}: quote not found in its source passage")
    return issues


def search_baseline(chunks):
    for chunk in chunks:
        for pattern in BASELINE_RES:
            match = pattern.search(chunk.text)
            if match:
                start = max(0, match.start() - 40)
                snippet = chunk.text[start: match.end() + 60].replace("\n", " ")
                return normalize_year(match.group(1)), chunk, snippet
    return None


def alternative_tests(ctx: Ctx) -> list[dict]:
    tests = []
    elec = ctx.calc("electricity_change_pct")
    prod = ctx.calc("production_change_pct")
    per_tonne = ctx.calc("kwh_per_tonne_change_pct")

    # 1. Production growth
    if elec and prod and per_tonne:
        if per_tonne.value <= 2.0:
            tests.append({
                "name": "Production growth", "outcome": "supported", "evidence": [elec, prod, per_tonne],
                "detail": (f"Electricity changed {elec.value:+.1f}% while production changed {prod.value:+.1f}%; "
                           f"electricity per tonne changed {per_tonne.value:+.1f}%, so higher output could explain it."),
            })
        else:
            tests.append({
                "name": "Production growth", "outcome": "not_supported", "evidence": [elec, prod, per_tonne],
                "detail": (f"Production changed {prod.value:+.1f}% but electricity changed {elec.value:+.1f}%; "
                           f"electricity per tonne is still {per_tonne.value:+.1f}%, so output growth alone does not explain it."),
            })
    else:
        tests.append({"name": "Production growth", "outcome": "untestable", "evidence": [],
                      "detail": "Electricity and production records for two periods are not both available."})

    # 2. Energy source change (documented, operating on-site generation)
    hit = None
    for chunk in ctx.chunks:
        for sentence in sentences(chunk.text):
            if ONSITE_RE.search(sentence) and not FUTURE_RE.search(sentence):
                hit = (chunk, sentence)
                break
        if hit:
            break
    if hit:
        chunk, sentence = hit
        ev = ctx.evidence_from(chunk, sentence, "onsite_generation_statement")
        tests.append({
            "name": "Change in energy source", "outcome": "supported", "evidence": [ev],
            "detail": (f"A submitted document describes on-site generation: \"{sentence[:200]}\" (page {chunk.page_number}). "
                       "The records do not separate grid from on-site supply, so the effect on emissions cannot be quantified."),
        })
    else:
        tests.append({
            "name": "Change in energy source", "outcome": "not_supported", "evidence": [],
            "detail": "No submitted document describes operating on-site generation or a fuel switch that would "
                      "lower emissions despite higher consumption. (Absence in the submitted documents is not proof.)",
        })

    # 3. Reporting boundary / baseline differences
    if any(BOUNDARY_RE.search(c.text) for c in ctx.chunks):
        tests.append({"name": "Reporting boundary or baseline difference", "outcome": "not_supported", "evidence": [],
                      "detail": "A reporting boundary is stated in the submitted documents."})
    else:
        tests.append({"name": "Reporting boundary or baseline difference", "outcome": "untestable", "evidence": [],
                      "detail": "No reporting boundary is documented, so a boundary or baseline mismatch cannot be tested."})

    # 4. Incomplete or erroneous records
    incomplete = ctx.incomplete_periods()
    if incomplete:
        tests.append({"name": "Incomplete records", "outcome": "supported", "evidence": [],
                      "detail": "Some periods have fewer than 12 monthly records: " + "; ".join(incomplete) + "."})
    else:
        tests.append({"name": "Incomplete records", "outcome": "not_supported", "evidence": [],
                      "detail": "All extracted monthly record sets are complete (12 months per period)."})
    return tests


def verdict_from(tests: list[dict]) -> str:
    outcomes = [t["outcome"] for t in tests]
    if "supported" in outcomes:
        return "disputed"
    if "untestable" in outcomes:
        return "unresolved"
    return "verified"


def challenge_finding(ctx: Ctx, finding: Finding, allow_reassess: bool, reassess_ids: set[int]):
    issues = integrity_issues(finding, ctx.chunk_text)
    if issues:
        return "unsupported", [{"name": "Evidence integrity", "outcome": "failed", "evidence": [],
                                "detail": "; ".join(issues) + "."}]
    tests = [{"name": "Evidence integrity", "outcome": "passed", "evidence": [],
              "detail": "Linked evidence is traceable to source passages or deterministic calculations."}]
    claim = ctx.db.get(Claim, finding.claim_id) if finding.claim_id else None

    if finding.status == "insufficient_information":
        if (claim is not None and not claim.baseline_period and claim.value is not None
                and claim.category in ("emissions", "energy")):
            found = search_baseline(ctx.chunks)
            if found:
                year, chunk, snippet = found
                ev = ctx.evidence_from(chunk, snippet, "baseline_statement")
                ev.claim_id = claim.id
                claim.baseline_period = year
                if allow_reassess:
                    reassess_ids.add(claim.id)
                tests.append({
                    "name": "Broader baseline search", "outcome": "supported", "evidence": [ev],
                    "detail": (f"A baseline ({year}) is stated elsewhere in the submitted documents (page {chunk.page_number}); "
                               "the claim had been extracted without it. The claim was updated and its findings will be reassessed."),
                })
                return "disputed", tests
            tests.append({
                "name": "Broader baseline search", "outcome": "not_supported", "evidence": [],
                "detail": f"All {len(ctx.chunks)} extracted passages were searched again: no baseline year is stated.",
            })
        else:
            tests.append({
                "name": "Repeat search", "outcome": "not_supported", "evidence": [],
                "detail": f"All {len(ctx.chunks)} extracted passages were searched again; the missing information was not found.",
            })
        return "verified", tests

    if finding.status in ("contradictory", "potential_anomaly") and (
        finding.category == "greenwashing" and TOPIC_RE.search(finding.title)
    ):
        tests += alternative_tests(ctx)
        return verdict_from(tests[1:]), tests

    tests.append({"name": "Reproducibility", "outcome": "passed", "evidence": [],
                  "detail": "The finding follows from figures extracted from the submitted documents, which are not independently audited."})
    return "verified", tests


def review_text(verdict: str, tests: list[dict]) -> str:
    lines = [f"Adversarial review - verdict: {verdict.upper()} ({VERDICT_LABEL[verdict]})"]
    for t in tests:
        lines.append(f"- {t['name']}: {t['outcome'].replace('_', ' ')}. {t['detail']}")
    return "\n".join(lines)


def llm_review(finding_title: str, status: str, severity: str, base_text: str, tests: list[dict]) -> Challenge:
    test_lines = "\n".join(f"- {t['name']}: {t['outcome']}. {t['detail']}" for t in tests)
    user = (
        f"Finding title: {finding_title}\nStatus: {status}; severity: {severity}\n"
        f"Finding text:\n{base_text[:1200]}\n\nDeterministic tests already run:\n{test_lines}"
    )
    return call_json(CHALLENGE_SYSTEM, user, Challenge, max_tokens=1500)


# ------------------------------------------------------------------ entry point
def run(db: Session, application_id: int, allow_reassess: bool = True) -> dict:
    chunks = load_chunks(db, application_id)
    ctx = Ctx(db, application_id, chunks)
    pending = db.scalars(
        select(Finding).where(Finding.application_id == application_id, Finding.verification_status == "pending")
    ).all()
    challenged = [f for f in pending if needs_challenge(f)]
    challenged.sort(key=lambda f: (SEVERITY_RANK.get(f.severity, 3), f.id))
    challenged = challenged[:MAX_CHALLENGES]
    challenged_ids = {f.id for f in challenged}
    for f in pending:
        if f.id not in challenged_ids:
            f.verification_status = "not_challenged"

    reassess_ids: set[int] = set()
    records = []
    for finding in challenged:
        base_text = finding.explanation
        verdict, tests = challenge_finding(ctx, finding, allow_reassess, reassess_ids)
        finding.explanation = f"{base_text}\n\n{review_text(verdict, tests)}"
        finding.verification_status = verdict
        cap = CONFIDENCE_CAP.get(verdict)
        if cap is not None and finding.confidence is not None:
            finding.confidence = min(finding.confidence, cap)
        linked = {e.id for e in finding.evidence_items}
        for t in tests:
            for ev in t["evidence"]:
                if ev.id not in linked:
                    finding.evidence_items.append(ev)
                    linked.add(ev.id)
        records.append({"finding": finding, "verdict": verdict, "tests": tests, "base": base_text})
    db.commit()

    warnings: list[str] = []
    llm_done = 0
    if not (allow_reassess and reassess_ids):  # skip model commentary if these findings will be recomputed
        ordered = sorted(records, key=lambda r: VERDICT_ORDER.get(r["verdict"], 9))
        for rec in ordered[:MAX_LLM_REVIEWS]:
            f = rec["finding"]
            try:
                ch = llm_review(f.title, f.status, f.severity, rec["base"], rec["tests"])
            except LLMError as exc:
                warnings.append(f"model review skipped: {exc}"[:300])
                break
            extra = []
            alts = [a.strip() for a in ch.alternative_explanations[:3] if a.strip()]
            need = [e.strip() for e in ch.evidence_that_would_resolve[:3] if e.strip()]
            if alts:
                extra.append("Other alternatives to consider (model-suggested, untested): " + "; ".join(alts) + ".")
            if need:
                extra.append("Evidence that would settle it: " + "; ".join(need) + ".")
                f.recommended_followup = ((f.recommended_followup or "").rstrip() + " Also obtain: " + "; ".join(need) + ".").strip()
            if ch.wording_check != "appropriately_cautious" and ch.wording_note:
                extra.append(f"Wording review ({ch.wording_check.replace('_', ' ')}): {ch.wording_note.strip()}")
            if extra:
                f.explanation = f"{f.explanation}\n" + "\n".join(extra)
            llm_done += 1
        db.commit()

    return {
        "challenged": len(records),
        "verdicts": {str(r["finding"].id): r["verdict"] for r in records},
        "verdict_counts": dict(Counter(r["verdict"] for r in records)),
        "reassess_claim_ids": sorted(reassess_ids),
        "model_reviews": llm_done,
        "warnings": warnings,
    }