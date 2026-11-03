import re
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Application, Document, DocumentChunk
from app.services.extraction import extract

ALLOWED_TYPES = {".pdf": "application/pdf", ".csv": "text/csv", ".txt": "text/plain"}
DOC_TYPES = {
    "financial_statement",
    "sustainability_report",
    "energy_records",
    "production_data",
    "other",
}
MAX_BYTES = 15 * 1024 * 1024


def guess_doc_type(filename: str) -> str:
    n = filename.lower()
    if "financ" in n:
        return "financial_statement"
    if "sustainab" in n or "esg" in n:
        return "sustainability_report"
    if "electric" in n or "energy" in n:
        return "energy_records"
    if "production" in n:
        return "production_data"
    return "other"


def store_upload(db: Session, application: Application, upload: UploadFile, doc_type: str | None) -> Document:
    name = Path(upload.filename or "upload").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(415, f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_TYPES)}")

    data = upload.file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 15 MB.")
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise HTTPException(400, "This file is not a valid PDF.")

    chosen_type = doc_type or guess_doc_type(name)
    if chosen_type not in DOC_TYPES:
        raise HTTPException(422, f"doc_type must be one of: {', '.join(sorted(DOC_TYPES))}")

    folder = Path(settings.UPLOAD_DIR) / str(application.id)
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    stored_path = folder / f"{uuid4().hex}_{safe_name}"
    stored_path.write_bytes(data)

    doc = Document(
        application_id=application.id,
        filename=name,
        stored_path=str(stored_path),
        doc_type=chosen_type,
        mime_type=ALLOWED_TYPES[ext],
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    process_document(db, doc)
    db.refresh(doc)
    return doc


def process_document(db: Session, doc: Document) -> None:
    doc_id = doc.id
    try:
        page_count, pieces = extract(Path(doc.stored_path))
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
        for index, (page_number, text) in enumerate(pieces):
            db.add(
                DocumentChunk(
                    document_id=doc_id,
                    page_number=page_number,
                    chunk_index=index,
                    text=text.replace("\x00", ""),
                )
            )
        doc.page_count = page_count
        doc.status = "processed"
        doc.error = None if pieces else "No extractable text found (scanned document?). OCR is not enabled."
        db.commit()
    except Exception as exc:  # keep the upload, record the failure
        db.rollback()
        failed = db.get(Document, doc_id)
        failed.status = "failed"
        failed.error = str(exc)[:500]
        db.commit()


def delete_application_files(application_id: int) -> None:
    shutil.rmtree(Path(settings.UPLOAD_DIR) / str(application_id), ignore_errors=True)