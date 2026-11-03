from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Document, DocumentChunk
from app.schemas.application import ChunkOut

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_or_404(db: Session, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


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
        raise HTTPException(404, "Stored file is missing")
    return FileResponse(path, media_type=doc.mime_type or "application/octet-stream", filename=doc.filename)