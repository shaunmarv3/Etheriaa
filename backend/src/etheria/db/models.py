"""ORM mappings. The schema itself lives in hand-written migrations; later
milestones add models here as they start using their tables."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True), dict[str, Any]: JSONB}


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str]
    password_hash: Mapped[str]
    display_name: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str]
    family_id: Mapped[uuid.UUID]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    replaced_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_agent: Mapped[str | None]


class AuditLog(Base):
    """Partitioned by month in the database; insert-only from the app."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())
    user_ref: Mapped[str | None]
    action: Mapped[str]
    resource_type: Mapped[str | None]
    resource_id: Mapped[str | None]
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None]
    details: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str]
    mime_type: Mapped[str]
    storage_key: Mapped[str]
    sha256: Mapped[str]
    size_bytes: Mapped[int]
    page_count: Mapped[int | None]
    doc_type: Mapped[str | None]
    status: Mapped[str] = mapped_column(server_default=text("'pending'"))
    report_date: Mapped[date | None]
    lab_name: Mapped[str | None]
    summary: Mapped[str | None]
    extracted: Mapped[dict[str, Any] | None]
    extraction_stats: Mapped[dict[str, Any] | None]
    error_code: Mapped[str | None]
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    processed_at: Mapped[datetime | None]


class DocumentChunk(Base):
    """`tsv` is a generated column in the database and is not mapped."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID]
    chunk_index: Mapped[int]
    page: Mapped[int | None]
    source_kind: Mapped[str]
    content: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    document_id: Mapped[uuid.UUID]
    test_name: Mapped[str]
    value_text: Mapped[str]
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None]
    ref_range_text: Mapped[str | None]
    ref_low: Mapped[Decimal | None] = mapped_column(Numeric)
    ref_high: Mapped[Decimal | None] = mapped_column(Numeric)
    flag: Mapped[str]
    report_date: Mapped[date | None]
    page: Mapped[int | None]


class Medication(Base):
    """`ingredients` stays empty at ingestion: names are resolved at read time (M4)."""

    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    document_id: Mapped[uuid.UUID | None]
    name_raw: Mapped[str]
    ingredients: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    dose: Mapped[str | None]
    frequency: Mapped[str | None]
    duration: Mapped[str | None]
    source: Mapped[str]
    report_date: Mapped[date | None]
