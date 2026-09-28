"""Documents and their extracted data (spec 5, 7). Every function expects a
session opened with `Database.for_user(user_id)` and also filters by user
explicitly: RLS is the second line of defence, not the only one."""

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.db.models import Document, DocumentChunk, LabResult, Medication
from etheria.ingestion.schemas import Classification, EmbeddedChunk, ValidatedExtraction
from etheria.retrieval.embedding import decode_vector


async def create(
    s: AsyncSession,
    *,
    user_id: UUID,
    filename: str,
    mime_type: str,
    storage_key: str,
    sha256: str,
    size_bytes: int,
    page_count: int,
) -> Document:
    doc = Document(
        id=uuid4(),
        user_id=user_id,
        filename=filename,
        mime_type=mime_type,
        storage_key=storage_key,
        sha256=sha256,
        size_bytes=size_bytes,
        page_count=page_count,
        status="pending",
    )
    s.add(doc)
    await s.flush()
    await s.refresh(doc)
    return doc


async def get(s: AsyncSession, user_id: UUID, document_id: UUID) -> Document | None:
    stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_by_sha(s: AsyncSession, user_id: UUID, sha256: str) -> Document | None:
    stmt = select(Document).where(Document.user_id == user_id, Document.sha256 == sha256)
    return (await s.execute(stmt)).scalar_one_or_none()


async def list_for_user(s: AsyncSession, user_id: UUID) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.uploaded_at.desc(), Document.id)
    )
    return list((await s.execute(stmt)).scalars())


async def delete(s: AsyncSession, user_id: UUID, document_id: UUID) -> str | None:
    """Deletes the row (chunks, lab rows and medications cascade). Returns the
    storage key so the caller can remove the file, or None if not found."""
    stmt = (
        sql_delete(Document)
        .where(Document.id == document_id, Document.user_id == user_id)
        .returning(Document.storage_key)
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def set_status(
    s: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    status: str,
    *,
    error_code: str | None = None,
) -> None:
    doc = await get(s, user_id, document_id)
    if doc is None:
        return
    doc.status = status
    doc.error_code = error_code
    if status in ("done", "failed"):
        doc.processed_at = func.now()


async def store_results(
    s: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    *,
    classification: Classification,
    validated: ValidatedExtraction,
    chunks: list[EmbeddedChunk],
    summary: str,
    stats: dict[str, Any],
) -> bool:
    """Everything in one transaction (spec 5.3 step 7). Returns False, writing
    nothing, when the document was deleted while it was being processed.
    Earlier rows for the document are replaced, so an activity retry after a
    partial failure cannot duplicate them."""
    locked = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    doc = (await s.execute(locked.with_for_update())).scalar_one_or_none()
    if doc is None:
        return False
    for model in (LabResult, Medication, DocumentChunk):
        await s.execute(sql_delete(model).where(model.document_id == document_id))

    report_date = classification.report_date
    if validated.lab_results:
        await s.execute(
            insert(LabResult),
            [
                {
                    **r.model_dump(),
                    "user_id": user_id,
                    "document_id": document_id,
                    "report_date": report_date,
                }
                for r in validated.lab_results
            ],
        )
    if validated.medications:
        source = (
            "discharge_summary"
            if classification.doc_type == "discharge_summary"
            else "prescription"
        )
        await s.execute(
            insert(Medication),
            [
                {
                    **m.model_dump(exclude={"page"}),
                    "user_id": user_id,
                    "document_id": document_id,
                    "ingredients": [],
                    "source": source,
                    "report_date": report_date,
                }
                for m in validated.medications
            ],
        )
    if chunks:
        await s.execute(
            insert(DocumentChunk),
            [
                {
                    "user_id": user_id,
                    "document_id": document_id,
                    "chunk_index": c.index,
                    "page": c.page,
                    "source_kind": c.source_kind,
                    "content": c.content,
                    "embedding": decode_vector(c.embedding_b64),
                }
                for c in chunks
            ],
        )

    doc.doc_type = classification.doc_type
    doc.report_date = report_date
    doc.lab_name = classification.lab_name
    doc.summary = summary
    doc.extracted = validated.details
    doc.extraction_stats = {**stats, **validated.stats.model_dump(), "chunks": len(chunks)}
    doc.status = "done"
    doc.error_code = None
    doc.processed_at = func.now()
    return True
