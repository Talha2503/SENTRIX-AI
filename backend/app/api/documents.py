import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Document, DocumentChunk
from app.schemas.application import ChunkOut

router = APIRouter(prefix="/documents", tags=["documents"])

SAMPLE_ROOT = Path(__file__).resolve().parent.parent.parent / "sample_data"


def get_document_or_404(db: Session, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


def sample_data_fallback(doc: Document) -> Path | None:
    """Demo cases: serve the original sample file when the uploaded copy no longer exists."""
    if not SAMPLE_ROOT.exists():
        return None
    company = doc.application.organization.name
    for folder in SAMPLE_ROOT.iterdir():
        info_file = folder / "case_info.json"
        if not info_file.exists():
            continue
        try:
            info = json.loads(info_file.read_text(encoding="utf-8"))
        except ValueError:
            continue
        candidate = folder / doc.filename
        if info.get("company") == company and candidate.is_file():
            return candidate
    return None


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
def get_chunks(document_id: int, db: Session = Depends(get_db)):
    get_document_or_404(db, document_id)
    return db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()


@router.get("/{document_id}/file")
def get_file(document_id: int, db: Session = Depends(get_db)):
    doc = get_document_or_404(db, document_id)
    path = Path(doc.stored_path)
    if not path.exists():
        fallback = sample_data_fallback(doc)
        if fallback is None:
            raise HTTPException(404, "The stored file is no longer available")
        path = fallback
    return FileResponse(path, media_type=doc.mime_type or "application/octet-stream", filename=doc.filename)