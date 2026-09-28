"""`uv run etheria worker`: the Temporal worker process (spec 3.1). Loads the
embedding model once at start, then polls the ingestion task queue."""

import asyncio

import structlog
from temporalio.worker import Worker

from etheria.core.crypto import encryption_key
from etheria.core.logging import configure_logging
from etheria.core.settings import Settings
from etheria.db.session import Database
from etheria.ingestion.activities import IngestionActivities
from etheria.ingestion.parse import tesseract_ocr
from etheria.ingestion.storage import FileStore
from etheria.ingestion.temporal import TASK_QUEUE, connect
from etheria.ingestion.workflow import IngestDocumentWorkflow
from etheria.llm.registry import structured_factory
from etheria.retrieval.embedding import BgeEmbedder

log = structlog.get_logger("etheria.worker")


async def run_worker(settings: Settings) -> None:
    configure_logging(settings.log_level)
    embedder = BgeEmbedder(settings.embedding_model)
    log.info("worker.loading_model", model=settings.embedding_model)
    await asyncio.to_thread(embedder.load)
    db = Database(settings.sqlalchemy_url)
    activities = IngestionActivities(
        db,
        FileStore(settings.upload_dir, encryption_key(settings)),
        embedder,
        structured_factory(settings),
        tesseract_ocr(settings.tesseract_cmd),
    )
    client = await connect(settings)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[IngestDocumentWorkflow],
        activities=activities.all(),
    )
    log.info("worker.started", task_queue=TASK_QUEUE, temporal=settings.temporal_address)
    try:
        await worker.run()
    finally:
        await db.dispose()
