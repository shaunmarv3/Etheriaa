"""Ingestion activities (spec 5.3): the I/O half of the workflow. Temporal
retries each one per the policy in workflow.py; they are written to be safe
to run again (store_results replaces earlier rows).

Parse and mask run in one activity: Temporal persists every activity's result
in its history, so unmasked text must never be an activity result."""

import asyncio
from collections.abc import Awaitable
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from etheria.db.repositories import documents as repo
from etheria.db.session import Database
from etheria.ingestion.chunking import chunk_pages
from etheria.ingestion.classify import classify_document as classify
from etheria.ingestion.extractors import extract_structured as extract
from etheria.ingestion.grounding import validate_lab_rows, validate_medications
from etheria.ingestion.labvalues import Sex
from etheria.ingestion.parse import OcrFn, OcrUnavailable, parse_document
from etheria.ingestion.pii_mask import mask_pii
from etheria.ingestion.schemas import (
    Classification,
    DocType,
    EmbeddedChunk,
    Extraction,
    IngestInput,
    PageText,
    ValidatedExtraction,
)
from etheria.ingestion.storage import FileStore
from etheria.ingestion.summary import summary_card
from etheria.llm.registry import StructuredFactory
from etheria.retrieval.embedding import Embedder, encode_vector

HEARTBEAT_EVERY_S = 5.0


async def _heartbeating[T](work: Awaitable[T]) -> T:
    """Heartbeat while slow work (OCR, embedding) runs in a thread, so the
    server can tell a busy worker from a dead one (heartbeat_timeout)."""
    task = asyncio.ensure_future(work)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=HEARTBEAT_EVERY_S)
            if done:
                return task.result()
            activity.heartbeat()
    except asyncio.CancelledError:
        task.cancel()
        raise


class IngestionActivities:
    def __init__(
        self,
        db: Database,
        store: FileStore,
        embedder: Embedder,
        make: StructuredFactory,
        ocr: OcrFn,
    ) -> None:
        self._db = db
        self._store = store
        self._embedder = embedder
        self._make = make
        self._ocr = ocr

    def all(self) -> list[Any]:
        return [
            self.mark_processing,
            self.parse_and_mask,
            self.classify_document,
            self.extract_structured,
            self.validate_and_flag,
            self.chunk_and_embed,
            self.store_results,
            self.mark_failed,
        ]

    @activity.defn
    async def mark_processing(self, inp: IngestInput) -> None:
        async with self._db.for_user(inp.user_id) as s:
            await repo.set_status(s, inp.user_id, inp.document_id, "processing")

    @activity.defn
    async def parse_and_mask(self, inp: IngestInput) -> list[PageText]:
        async with self._db.for_user(inp.user_id) as s:
            doc = await repo.get(s, inp.user_id, inp.document_id)
        if doc is None:
            raise ApplicationError("document deleted", type="document_missing", non_retryable=True)
        try:
            data = await asyncio.to_thread(self._store.read, doc.storage_key)
            pages = await _heartbeating(
                asyncio.to_thread(parse_document, data, doc.mime_type, self._ocr)
            )
        except FileNotFoundError:
            raise ApplicationError(
                "file missing", type="document_missing", non_retryable=True
            ) from None
        except OcrUnavailable:
            raise ApplicationError(
                "OCR is not available on this worker", type="ocr_unavailable", non_retryable=True
            ) from None
        return [p.model_copy(update={"text": mask_pii(p.text).text}) for p in pages]

    @activity.defn
    async def classify_document(self, pages: list[PageText]) -> Classification:
        return await classify(pages, self._make)

    @activity.defn
    async def extract_structured(self, doc_type: DocType, pages: list[PageText]) -> Extraction:
        return await extract(doc_type, pages, self._make)

    @activity.defn
    async def validate_and_flag(
        self, extraction: Extraction, pages: list[PageText], sex: Sex | None
    ) -> ValidatedExtraction:
        texts = {p.page: p.text for p in pages}
        rows, stats = validate_lab_rows(extraction.lab_rows, texts, sex)
        meds = validate_medications(extraction.medications, texts, stats)
        return ValidatedExtraction(
            lab_results=rows, medications=meds, details=extraction.details, stats=stats
        )

    @activity.defn
    async def chunk_and_embed(self, pages: list[PageText]) -> list[EmbeddedChunk]:
        def work() -> list[EmbeddedChunk]:
            chunks = chunk_pages(pages, self._embedder.count_tokens)
            if not chunks:
                return []
            vectors = self._embedder.embed_documents([c.content for c in chunks])
            return [
                EmbeddedChunk(**c.model_dump(), embedding_b64=encode_vector(v))
                for c, v in zip(chunks, vectors, strict=True)
            ]

        return await _heartbeating(asyncio.to_thread(work))

    @activity.defn
    async def store_results(
        self,
        inp: IngestInput,
        classification: Classification,
        validated: ValidatedExtraction,
        chunks: list[EmbeddedChunk],
        page_stats: dict[str, int],
    ) -> bool:
        summary = summary_card(classification, validated.lab_results, classification.doc_type)
        async with self._db.for_user(inp.user_id) as s:
            return await repo.store_results(
                s,
                inp.user_id,
                inp.document_id,
                classification=classification,
                validated=validated,
                chunks=chunks,
                summary=summary,
                stats=page_stats,
            )

    @activity.defn
    async def mark_failed(self, inp: IngestInput, error_code: str) -> None:
        async with self._db.for_user(inp.user_id) as s:
            await repo.set_status(s, inp.user_id, inp.document_id, "failed", error_code=error_code)
