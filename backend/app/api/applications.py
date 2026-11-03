from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Application, Document, DocumentChunk, Organization
from app.schemas.application import (
    ApplicationCreate,
    ApplicationOut,
    DocumentOut,
    SearchHit,
)
from app.services.documents import delete_application_files, store_upload

router = APIRouter(prefix="/applications", tags=["applications"])


def get_application_or_404(db: Session, application_id: int) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    return application


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    org = Organization(**payload.organization.model_dump())
    db.add(org)
    db.flush()
    row = Application(
        organization_id=org.id,
        title=payload.title,
        project_description=payload.project_description,
        requested_amount=payload.requested_amount,
        currency=payload.currency,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    return db.scalars(select(Application).order_by(Application.id.desc())).all()


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, db: Session = Depends(get_db)):
    return get_application_or_404(db, application_id)


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    application = get_application_or_404(db, application_id)
    db.delete(application)
    db.commit()
    delete_application_files(application_id)


@router.post("/{application_id}/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    application_id: int,
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
    db: Session = Depends(get_db),
):
    application = get_application_or_404(db, application_id)
    return store_upload(db, application, file, doc_type)


@router.get("/{application_id}/documents", response_model=list[DocumentOut])
def list_documents(application_id: int, db: Session = Depends(get_db)):
    get_application_or_404(db, application_id)
    return db.scalars(
        select(Document).where(Document.application_id == application_id).order_by(Document.id)
    ).all()


@router.get("/{application_id}/search", response_model=list[SearchHit])
def search_evidence(
    application_id: int,
    q: str = Query(min_length=2),
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Full-text search over this application's extracted document chunks."""
    get_application_or_404(db, application_id)
    ts_query = func.websearch_to_tsquery("english", q)
    vector = func.to_tsvector("english", DocumentChunk.text)
    rank = func.ts_rank(vector, ts_query)
    stmt = (
        select(DocumentChunk, Document.filename, rank.label("rank"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.application_id == application_id, vector.op("@@")(ts_query))
        .order_by(rank.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            rank=float(score),
            text=chunk.text,
        )
        for chunk, filename, score in db.execute(stmt).all()
    ]