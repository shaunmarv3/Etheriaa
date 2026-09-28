from decimal import Decimal
from uuid import uuid4

import psycopg
from ingestion_fakes import new_user
from sqlalchemy import func, select

from etheria.db.models import DocumentChunk, LabResult, Medication
from etheria.db.repositories import documents as repo
from etheria.db.session import Database
from etheria.ingestion.schemas import (
    Classification,
    EmbeddedChunk,
    GroundingStats,
    LabResultRow,
    PagedMedication,
    ValidatedExtraction,
)
from etheria.retrieval.embedding import encode_vector

CLS = Classification(doc_type="discharge_summary", lab_name="Greenfield", confidence=0.9)
VALIDATED = ValidatedExtraction(
    lab_results=[
        LabResultRow(
            test_name="Haemoglobin",
            value_text="10.9",
            value_numeric=Decimal("10.9"),
            unit="g/dL",
            ref_range_text="13.0 - 17.0",
            ref_low=Decimal("13.0"),
            ref_high=Decimal("17.0"),
            flag="low",
            page=1,
        )
    ],
    medications=[PagedMedication(name_raw="Pan 40", frequency="once daily", page=1)],
    details={"diagnoses": ["Pneumonia"], "procedures": [], "follow_up": None},
    stats=GroundingStats(rows_extracted=1),
)
CHUNKS = [
    EmbeddedChunk(
        index=i,
        page=1,
        source_kind="text_layer",
        content=f"chunk {i}",
        embedding_b64=encode_vector([1.0] + [0.0] * 1023),
    )
    for i in range(3)
]


async def make_doc(db: Database, user_id):
    async with db.for_user(user_id) as s:
        return await repo.create(
            s,
            user_id=user_id,
            filename="r.pdf",
            mime_type="application/pdf",
            storage_key=uuid4().hex,
            sha256=uuid4().hex,
            size_bytes=10,
            page_count=1,
        )


async def store(db: Database, user_id, doc_id) -> bool:
    async with db.for_user(user_id) as s:
        return await repo.store_results(
            s,
            user_id,
            doc_id,
            classification=CLS,
            validated=VALIDATED,
            chunks=CHUNKS,
            summary="Discharge summary",
            stats={"pages": 1},
        )


async def counts(db: Database, user_id, doc_id) -> tuple[int, int, int]:
    out = []
    async with db.for_user(user_id) as s:
        for m in (LabResult, Medication, DocumentChunk):
            stmt = select(func.count()).select_from(m).where(m.document_id == doc_id)
            out.append((await s.execute(stmt)).scalar_one())
    return tuple(out)


async def test_store_results_writes_rows_and_done(db: Database, owner_conn: psycopg.Connection):
    uid = new_user(owner_conn)
    doc = await make_doc(db, uid)
    assert await store(db, uid, doc.id)
    assert await counts(db, uid, doc.id) == (1, 1, 3)
    async with db.for_user(uid) as s:
        d = await repo.get(s, uid, doc.id)
        med = (await s.execute(select(Medication))).scalar_one()
        lab = (await s.execute(select(LabResult))).scalar_one()
    assert d.status == "done" and d.processed_at is not None
    assert d.doc_type == "discharge_summary" and d.lab_name == "Greenfield"
    assert d.summary == "Discharge summary"
    assert d.extracted == VALIDATED.details
    assert d.extraction_stats["pages"] == 1 and d.extraction_stats["rows_extracted"] == 1
    assert d.extraction_stats["chunks"] == 3
    assert med.ingredients == [] and med.source == "discharge_summary"
    assert lab.flag == "low" and lab.value_numeric == Decimal("10.9")


async def test_store_results_is_idempotent(db: Database, owner_conn: psycopg.Connection):
    uid = new_user(owner_conn)
    doc = await make_doc(db, uid)
    await store(db, uid, doc.id)
    await store(db, uid, doc.id)
    assert await counts(db, uid, doc.id) == (1, 1, 3)


async def test_store_skips_deleted_document(db: Database, owner_conn: psycopg.Connection):
    uid = new_user(owner_conn)
    doc = await make_doc(db, uid)
    async with db.for_user(uid) as s:
        assert await repo.delete(s, uid, doc.id) == doc.storage_key
    assert await store(db, uid, doc.id) is False
    assert await counts(db, uid, doc.id) == (0, 0, 0)


async def test_rls_hides_other_users_documents(db: Database, owner_conn: psycopg.Connection):
    a, b = new_user(owner_conn), new_user(owner_conn)
    doc = await make_doc(db, a)
    await store(db, a, doc.id)
    async with db.for_user(b) as s:
        assert await repo.get(s, b, doc.id) is None
        assert await repo.list_for_user(s, b) == []
        assert await repo.delete(s, b, doc.id) is None
    assert await counts(db, b, doc.id) == (0, 0, 0)
    assert await counts(db, a, doc.id) == (1, 1, 3)


async def test_set_status_failed_with_code(db: Database, owner_conn: psycopg.Connection):
    uid = new_user(owner_conn)
    doc = await make_doc(db, uid)
    async with db.for_user(uid) as s:
        await repo.set_status(s, uid, doc.id, "failed", error_code="ocr_unavailable")
    async with db.for_user(uid) as s:
        d = await repo.get(s, uid, doc.id)
    assert (d.status, d.error_code) == ("failed", "ocr_unavailable")
    assert d.processed_at is not None


async def test_get_by_sha_is_per_user(db: Database, owner_conn: psycopg.Connection):
    a, b = new_user(owner_conn), new_user(owner_conn)
    doc = await make_doc(db, a)
    async with db.for_user(a) as s:
        assert (await repo.get_by_sha(s, a, doc.sha256)).id == doc.id
    async with db.for_user(b) as s:
        assert await repo.get_by_sha(s, b, doc.sha256) is None
