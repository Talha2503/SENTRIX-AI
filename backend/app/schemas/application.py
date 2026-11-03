from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sector: str | None = None
    location: str | None = None
    country: str = "Pakistan"
    description: str | None = None


class OrganizationOut(OrganizationIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ApplicationCreate(BaseModel):
    organization: OrganizationIn
    title: str = Field(min_length=1, max_length=255)
    project_description: str | None = None
    requested_amount: float | None = None
    currency: str = "PKR"


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    filename: str
    doc_type: str
    mime_type: str | None = None
    page_count: int | None = None
    status: str
    error: str | None = None
    uploaded_at: datetime


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    project_description: str | None = None
    requested_amount: float | None = None
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime
    organization: OrganizationOut
    documents: list[DocumentOut] = []


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    page_number: int | None = None
    chunk_index: int
    text: str


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    filename: str
    page_number: int | None = None
    chunk_index: int
    rank: float
    text: str