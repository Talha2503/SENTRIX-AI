"""Document Intelligence agent.

LLM: extracts environmental claims from narrative text (quotes verified against the source chunk).
Code: parses tables and monthly CSV records into numeric evidence (no LLM arithmetic).
"""
import csv
import re
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm import LLMError, call_json
from app.models.models import Claim, Document, DocumentChunk, Evidence

BATCH_CHARS = 6000
LLM_DOC_TYPES = {"sustainability_report", "other"}

HEADER_RE = re.compile(r"^(?P<unit>.*?)\s*(?P<p1>FY\d{4})\s+(?P<p2>FY\d{4})\s*$")
ROW_RE = re.compile(r"^(?P<label>.+?)\s+(?P<a>-?[\d,]+(?:\.\d+)?)\s+(?P<b>-?[\d,]+(?:\.\d+)?)\s*$")
PAREN_RE = re.compile(r"\s*\(([^)]*)\)\s*$")

METRIC_ALIASES = {
    "electricity_consumed": "electricity_kwh",
    "production": "production_tonnes",
    "emissions": "emissions_t_co2e",
    "electricity_per_tonne": "kwh_per_tonne",
    "shareholders_equity": "equity",
    "net_cash_from_operating_activities": "operating_cash_flow",
}
UNIT_SUFFIX = {"kwh": "kWh", "mwh": "MWh", "tonnes": "tonnes", "pkr": "PKR"}

SYSTEM_PROMPT = """You are the Document Intelligence agent of a green-finance due-diligence platform.
Extract the environmental or sustainability claims a company makes in the text.
Rules:
- Only extract claims the company makes about its own environmental performance, its practices, or the expected effects of its financed project. Ignore headings, addresses and boilerplate.
- source_quote must be copied VERBATIM from the chunk (one sentence or fragment). Never paraphrase it.
- chunk_id must be the id of the chunk the quote comes from.
- value: a signed number only if the claim states one (a 40% reduction is -40 with unit "%"). Otherwise null.
- reporting_period: only if stated in the text. baseline_period: ONLY if a baseline or comparison year is explicitly stated. Never infer or guess a baseline. Use null when absent.
- category: emissions, energy, production, financial, practice (operational or process claims), projection (expected future effects), other.
- Do not judge whether a claim is true. Do not add claims that are not in the text."""


class ExtractedClaim(BaseModel):
    chunk_id: int
    source_quote: str
    claim_text: str
    category: Literal["emissions", "energy", "production", "financial", "practice", "projection", "other"]
    value: float | None = None
    unit: str | None = None
    reporting_period: str | None = None
    baseline_period: str | None = None


class ClaimExtraction(BaseModel):
    claims: list[ExtractedClaim] = []


def norm(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def make_batches(chunks: list[DocumentChunk]) -> list[list[DocumentChunk]]:
    batches, current, size = [], [], 0
    for chunk in chunks:
        if current and size + len(chunk.text) > BATCH_CHARS:
            batches.append(current)
            current, size = [], 0
        current.append(chunk)
        size += len(chunk.text)
    if current:
        batches.append(current)
    return batches


# ------------------------------------------------------------ LLM claim extraction
def extract_claims_llm(db: Session, doc: Document, chunks: list[DocumentChunk]) -> dict:
    kept = rejected = cleared = 0
    method = f"llm:{settings.GROQ_MODEL}"
    for batch in make_batches(chunks):
        by_id = {c.id: c for c in batch}
        body = "\n\n".join(f"[chunk_id={c.id} page={c.page_number}]\n{c.text}" for c in batch)
        result = call_json(SYSTEM_PROMPT, f"Extract the claims from these chunks.\n\n{body}", ClaimExtraction)
        for item in result.claims:
            chunk = by_id.get(item.chunk_id)
            quote = item.source_quote.strip()
            if chunk is None or not quote or norm(quote) not in norm(chunk.text):
                rejected += 1  # quote is not verbatim in the cited chunk
                continue
            baseline, period = item.baseline_period, item.reporting_period
            if baseline and norm(baseline) not in norm(chunk.text):
                baseline, cleared = None, cleared + 1  # model invented a baseline
            if period and norm(period) not in norm(chunk.text):
                period, cleared = None, cleared + 1
            claim = Claim(
                application_id=doc.application_id,
                document_id=doc.id,
                chunk_id=chunk.id,
                claim_text=item.claim_text.strip(),
                source_quote=quote[:1000],
                category=item.category,
                value=item.value,
                unit=item.unit,
                reporting_period=period,
                baseline_period=baseline,
                page_number=chunk.page_number,
                status="unverified",
                extraction_method=method,
            )
            db.add(claim)
            db.flush()
            db.add(
                Evidence(
                    application_id=doc.application_id,
                    document_id=doc.id,
                    chunk_id=chunk.id,
                    claim_id=claim.id,
                    page_number=chunk.page_number,
                    excerpt=quote[:1000],
                    evidence_type="claim_source",
                    extraction_method=method,
                )
            )
            kept += 1
    db.commit()
    return {"claims_kept": kept, "claims_rejected": rejected, "ungrounded_fields_cleared": cleared}


# ------------------------------------------------------------ deterministic table parsing
def parse_label(label: str, default_unit: str | None) -> tuple[str, str | None]:
    unit = default_unit
    match = PAREN_RE.search(label)
    if match:
        unit = match.group(1).strip()
        label = label[: match.start()]
    key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return METRIC_ALIASES.get(key, key), unit


def extract_tables(db: Session, doc: Document, chunks: list[DocumentChunk]) -> int:
    table = None  # (period1, period2, default_unit)
    count = 0
    for chunk in chunks:
        for line in chunk.text.splitlines():
            text = line.strip()
            header = HEADER_RE.match(text)
            if header:
                unit_text = header.group("unit").strip()
                default_unit = unit_text if re.search(r"PKR|million", unit_text, re.I) else None
                table = (header.group("p1"), header.group("p2"), default_unit)
                continue
            if table is None:
                continue
            if not text or set(text) <= {"-"}:
                continue
            row = ROW_RE.match(text)
            if not row:
                table = None
                continue
            metric, unit = parse_label(row.group("label"), table[2])
            for period, raw in ((table[0], row.group("a")), (table[1], row.group("b"))):
                db.add(
                    Evidence(
                        application_id=doc.application_id,
                        document_id=doc.id,
                        chunk_id=chunk.id,
                        page_number=chunk.page_number,
                        excerpt=text[:500],
                        evidence_type="contextual",
                        metric=metric,
                        value=float(raw.replace(",", "")),
                        unit=unit,
                        reporting_period=period,
                        extraction_method="table_parser",
                    )
                )
                count += 1
    db.commit()
    return count


# ------------------------------------------------------------ deterministic CSV totals
def extract_csv_totals(db: Session, doc: Document, chunks: list[DocumentChunk]) -> dict:
    sums: dict[tuple[str, str], list] = {}  # (metric, fy) -> [total, months, first_chunk_id]
    for chunk in chunks:
        lines = [ln for ln in chunk.text.splitlines() if ln.strip() and not ln.startswith("#")]
        if len(lines) < 2:
            continue
        rows = list(csv.reader(lines))
        header = [h.strip().lower() for h in rows[0]]
        if "fiscal_year" not in header:
            continue
        fy_idx = header.index("fiscal_year")
        for row in rows[1:]:
            if len(row) != len(header):
                continue
            for idx, name in enumerate(header):
                try:
                    value = float(row[idx])
                except ValueError:
                    continue  # month label, fiscal year, text columns
                entry = sums.setdefault((name, row[fy_idx].strip()), [0.0, 0, chunk.id])
                entry[0] += value
                entry[1] += 1

    incomplete = []
    for (metric, fy), (total, months, chunk_id) in sums.items():
        unit = UNIT_SUFFIX.get(metric.split("_")[-1])
        if months != 12:
            incomplete.append(f"{metric} {fy}: {months} of 12 months")
        db.add(
            Evidence(
                application_id=doc.application_id,
                document_id=doc.id,
                chunk_id=chunk_id,
                excerpt=f"{metric} {fy}: sum of {months} monthly rows = {total:,.0f} {unit or ''}".strip(),
                evidence_type="contextual",
                metric=metric,
                value=total,
                unit=unit,
                reporting_period=fy,
                extraction_method="csv_sum",
            )
        )
    db.commit()
    return {"evidence": len(sums), "incomplete_periods": incomplete}


# ------------------------------------------------------------ entry point
def run(db: Session, application_id: int) -> dict:
    docs = db.scalars(
        select(Document)
        .where(Document.application_id == application_id, Document.status == "processed")
        .order_by(Document.id)
    ).all()
    summary = {"documents": [], "claims_kept": 0, "claims_rejected": 0, "numeric_evidence": 0,
               "incomplete_periods": [], "warnings": []}

    for doc in docs:
        chunks = db.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index)
        ).all()
        info = {"document_id": doc.id, "filename": doc.filename, "doc_type": doc.doc_type}

        if doc.mime_type == "text/csv":
            result = extract_csv_totals(db, doc, chunks)
            info["numeric_evidence"] = result["evidence"]
            summary["numeric_evidence"] += result["evidence"]
            summary["incomplete_periods"] += result["incomplete_periods"]
        else:
            table_count = extract_tables(db, doc, chunks)
            info["numeric_evidence"] = table_count
            summary["numeric_evidence"] += table_count
            if doc.doc_type in LLM_DOC_TYPES:
                try:
                    result = extract_claims_llm(db, doc, chunks)
                    info.update(result)
                    summary["claims_kept"] += result["claims_kept"]
                    summary["claims_rejected"] += result["claims_rejected"]
                except LLMError as exc:
                    db.rollback()
                    info["llm_error"] = str(exc)[:300]
                    summary["warnings"].append(f"{doc.filename}: claim extraction failed ({exc})"[:400])
        summary["documents"].append(info)
    return summary