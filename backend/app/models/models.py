from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

finding_evidence = Table(
    "finding_evidence",
    Base.metadata,
    Column("finding_id", ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(80), default="Pakistan")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    applications: Mapped[list["Application"]] = relationship(back_populates="organization")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    project_description: Mapped[str | None] = mapped_column(Text)
    requested_amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="PKR")
    # draft | processing | investigating | completed | failed
    status: Mapped[str] = mapped_column(String(30), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="applications")
    documents: Mapped[list["Document"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    claims: Mapped[list["Claim"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    # financial_statement | sustainability_report | energy_records | production_data | other
    doc_type: Mapped[str] = mapped_column(String(50), default="other")
    mime_type: Mapped[str | None] = mapped_column(String(100))
    page_count: Mapped[int | None] = mapped_column(Integer)
    # uploaded | processing | processed | failed
    status: Mapped[str] = mapped_column(String(30), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"))
    claim_text: Mapped[str] = mapped_column(Text)
    source_quote: Mapped[str | None] = mapped_column(Text)
    # emissions | energy | production | financial | practice | projection | other
    category: Mapped[str] = mapped_column(String(50), default="other")
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50))
    reporting_period: Mapped[str | None] = mapped_column(String(80))
    baseline_period: Mapped[str | None] = mapped_column(String(80))
    page_number: Mapped[int | None] = mapped_column(Integer)
    # verified | unverified | contradictory | potential_anomaly | insufficient_information | not_assessed
    status: Mapped[str] = mapped_column(String(40), default="unverified")
    extraction_method: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="claims")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"))
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    excerpt: Mapped[str | None] = mapped_column(Text)
    # claim_source | contextual | supporting | conflicting | calculation
    evidence_type: Mapped[str] = mapped_column(String(30), default="contextual")
    metric: Mapped[str | None] = mapped_column(String(80))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50))
    reporting_period: Mapped[str | None] = mapped_column(String(80))
    extraction_method: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="evidence")

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(String(80))
    task: Mapped[str | None] = mapped_column(Text)
    input_refs: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    # pending | running | completed | failed
    status: Mapped[str] = mapped_column(String(30), default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    application: Mapped["Application"] = relationship(back_populates="agent_runs")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"))
    agent_name: Mapped[str] = mapped_column(String(80))
    # greenwashing | taxonomy | financial | climate | data_quality
    category: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    explanation: Mapped[str] = mapped_column(Text)
    # low | medium | high
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    # verified | unverified | contradictory | potential_anomaly | insufficient_information | not_assessed
    status: Mapped[str] = mapped_column(String(40), default="unverified")
    # verification: verified | disputed | unresolved | unsupported | pending
    verification_status: Mapped[str] = mapped_column(String(30), default="pending")
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_notes: Mapped[str | None] = mapped_column(Text)
    recommended_followup: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="findings")
    evidence_items: Mapped[list["Evidence"]] = relationship(secondary=finding_evidence)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    calculation_version: Mapped[str] = mapped_column(String(30), default="v1")
    dimension_scores: Mapped[dict | None] = mapped_column(JSONB)
    coverage: Mapped[dict | None] = mapped_column(JSONB)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    limitations: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="assessments")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict | None] = mapped_column(JSONB)
    # pending_review | reviewed
    review_status: Mapped[str] = mapped_column(String(30), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="reports")