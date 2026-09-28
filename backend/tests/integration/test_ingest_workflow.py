"""The ingestion workflow end to end against the Temporal dev server (docker),
the real test database, fake models and a fake embedder.

Temporal concepts: the workflow is replayed deterministically from history;
activities do the I/O and are retried per policy. Each test runs its own
in-process worker on a unique task queue, so tests never steal each other's
tasks."""

import asyncio
import threading
from pathlib import Path
from uuid import uuid4

import psycopg
from ingestion_fakes import EXPECTED, REPORTS, FakeEmbedder, FakeOcr, FixtureModels, new_user
from sqlalchemy import select
from temporalio.worker import Worker

from etheria.core.settings import Settings
from etheria.db.models import DocumentChunk, LabResult
from etheria.db.repositories import documents as repo
from etheria.db.session import Database
from etheria.ingestion.activities import IngestionActivities
from etheria.ingestion.parse import OcrUnavailable
from etheria.ingestion.schemas import IngestInput
from etheria.ingestion.storage import FileStore
from etheria.ingestion.temporal import connect, workflow_id
from etheria.ingestion.validation import inspect_upload
from etheria.ingestion.workflow import IngestDocumentWorkflow

KEY = bytes(range(32))


class CountingStore(FileStore):
    """Counts file reads: parse_and_mask is the only activity that reads the file."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, KEY)
        self.reads = 0

    def read(self, storage_key: str) -> bytes:
        self.reads += 1
        return super().read(storage_key)


async def upload(db: Database, owner_conn, store: FileStore, fixture: str):
    uid = new_user(owner_conn)
    data = (REPORTS / fixture).read_bytes()
    info = inspect_upload(data, fixture)
    async with db.for_user(uid) as s:
        doc = await repo.create(
            s,
            user_id=uid,
            filename=info.display_name,
            mime_type=info.mime_type,
            storage_key=store.save(data),
            sha256=info.sha256,
            size_bytes=len(data),
            page_count=info.page_count,
        )
    return uid, doc


async def run_ingest(settings: Settings, acts: IngestionActivities, uid, doc_id):
    client = await connect(settings)
    queue = f"test-ingest-{uuid4().hex}"
    async with Worker(
        client, task_queue=queue, workflows=[IngestDocumentWorkflow], activities=acts.all()
    ):
        return await client.execute_workflow(
            IngestDocumentWorkflow.run,
            IngestInput(document_id=doc_id, user_id=uid),
            id=workflow_id(doc_id),
            task_queue=queue,
        )


async def load(db: Database, uid, doc_id):
    async with db.for_user(uid) as s:
        doc = await repo.get(s, uid, doc_id)
        labs = list((await s.execute(select(LabResult))).scalars())
        chunks = list((await s.execute(select(DocumentChunk))).scalars())
    return doc, labs, chunks


async def test_workflow_happy_path_lab_report(
    settings: Settings, db: Database, owner_conn: psycopg.Connection, tmp_path: Path
):
    store = CountingStore(tmp_path)
    uid, doc = await upload(db, owner_conn, store, "lab_cbc.pdf")
    acts = IngestionActivities(db, store, FakeEmbedder(), FixtureModels("lab_cbc.pdf"), FakeOcr())
    outcome = await run_ingest(settings, acts, uid, doc.id)
    assert outcome.status == "done"
    doc, labs, chunks = await load(db, uid, doc.id)
    expected = {r["test_name"]: r["flag"] for r in EXPECTED["lab_cbc.pdf"]["lab_rows"]}
    assert {lab.test_name: lab.flag for lab in labs} == expected
    assert doc.status == "done" and doc.doc_type == "lab_report"
    assert doc.summary.startswith("Test report - Northwind Diagnostics")
    assert doc.extraction_stats["rows_dropped_ungrounded"] == 0
    assert doc.extraction_stats["text_layer_pages"] == 1
    assert chunks and {c.source_kind for c in chunks} == {"text_layer"}
    # Chunks hold masked text only.
    assert all("Rahul Verma" not in c.content and "98765" not in c.content for c in chunks)


async def test_workflow_scan_has_no_lab_rows(
    settings: Settings, db: Database, owner_conn: psycopg.Connection, tmp_path: Path
):
    store = CountingStore(tmp_path)
    uid, doc = await upload(db, owner_conn, store, "lab_cbc_scan.png")
    models = FixtureModels("lab_cbc_scan.png")
    acts = IngestionActivities(db, store, FakeEmbedder(), models, FakeOcr())
    outcome = await run_ingest(settings, acts, uid, doc.id)
    assert outcome.status == "done"
    doc, labs, chunks = await load(db, uid, doc.id)
    assert labs == []
    assert [c.source_kind for c in chunks] == ["ocr"]
    assert doc.extraction_stats["ocr_pages"] == 1
    assert "extract_lab_report" not in models.calls


async def test_workflow_failure_marks_failed(
    settings: Settings, db: Database, owner_conn: psycopg.Connection, tmp_path: Path
):
    store = CountingStore(tmp_path)
    uid, doc = await upload(db, owner_conn, store, "lab_cbc.pdf")
    models = FixtureModels("lab_cbc.pdf", fail="classify_document")
    acts = IngestionActivities(db, store, FakeEmbedder(), models, FakeOcr())
    outcome = await run_ingest(settings, acts, uid, doc.id)
    assert (outcome.status, outcome.error_code) == ("failed", "ingestion_failed")
    assert models.calls["classify_document"] == 3
    doc, labs, chunks = await load(db, uid, doc.id)
    assert (doc.status, doc.error_code) == ("failed", "ingestion_failed")
    assert labs == [] and chunks == []


async def test_ocr_unavailable_fails_fast(
    settings: Settings, db: Database, owner_conn: psycopg.Connection, tmp_path: Path
):
    store = CountingStore(tmp_path)
    uid, doc = await upload(db, owner_conn, store, "lab_cbc_scan.png")
    ocr = FakeOcr(fail=OcrUnavailable("tesseract not found"))
    acts = IngestionActivities(db, store, FakeEmbedder(), FixtureModels("lab_cbc.pdf"), ocr)
    outcome = await run_ingest(settings, acts, uid, doc.id)
    assert (outcome.status, outcome.error_code) == ("failed", "ocr_unavailable")
    assert store.reads == 1  # non-retryable: parse ran once
    doc, _, _ = await load(db, uid, doc.id)
    assert doc.error_code == "ocr_unavailable"


class BlockingEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.started.set()
        self.release.wait(timeout=120)
        return super().embed_documents(texts)


async def test_workflow_survives_worker_restart(
    settings: Settings, db: Database, owner_conn: psycopg.Connection, tmp_path: Path
):
    """Kill the worker in the middle of chunk_and_embed; a new worker finishes
    the run, and the steps that already completed are not repeated."""
    store = CountingStore(tmp_path)
    uid, doc = await upload(db, owner_conn, store, "lab_cbc.pdf")
    blocking = BlockingEmbedder()
    client = await connect(settings)
    queue = f"test-ingest-{uuid4().hex}"
    models = FixtureModels("lab_cbc.pdf")

    worker1 = Worker(
        client,
        task_queue=queue,
        workflows=[IngestDocumentWorkflow],
        activities=IngestionActivities(db, store, blocking, models, FakeOcr()).all(),
    )
    run1 = asyncio.create_task(worker1.run())
    handle = await client.start_workflow(
        IngestDocumentWorkflow.run,
        IngestInput(document_id=doc.id, user_id=uid),
        id=workflow_id(doc.id),
        task_queue=queue,
    )
    assert await asyncio.to_thread(blocking.started.wait, 30)
    await worker1.shutdown()
    await run1
    blocking.release.set()

    async with db.for_user(uid) as s:
        assert (await repo.get(s, uid, doc.id)).status == "processing"

    acts2 = IngestionActivities(db, store, FakeEmbedder(), models, FakeOcr())
    async with Worker(
        client, task_queue=queue, workflows=[IngestDocumentWorkflow], activities=acts2.all()
    ):
        outcome = await asyncio.wait_for(handle.result(), timeout=90)
    assert outcome.status == "done"
    assert store.reads == 1  # parse_and_mask ran exactly once
    assert models.calls["classify_document"] == 1
    _, labs, chunks = await load(db, uid, doc.id)
    assert len(labs) == len(EXPECTED["lab_cbc.pdf"]["lab_rows"]) and chunks
