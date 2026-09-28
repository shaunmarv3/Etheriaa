"""IngestDocumentWorkflow (spec 5.3): deterministic orchestration only.

Temporal replays this code from its event history after a worker restart, so
it must not do I/O, read the clock or use randomness: all of that happens in
activities. A step that already completed is not run again after a restart;
its recorded result is replayed instead."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from etheria.ingestion.activities import IngestionActivities as A
    from etheria.ingestion.schemas import Extraction, IngestInput, IngestOutcome, PageText

# Retry policies from spec 5.3. Deterministic steps get a single attempt.
ONCE = RetryPolicy(maximum_attempts=1)
THREE = RetryPolicy(maximum_attempts=3)
FIVE = RetryPolicy(maximum_attempts=5)
HEARTBEAT = timedelta(seconds=30)

# Error codes an activity may raise on purpose (ApplicationError.type); any
# other failure is reported as the generic code.
KNOWN_ERRORS = {"ocr_unavailable", "document_missing"}


def page_stats(pages: list[PageText], ext: Extraction) -> dict[str, int]:
    text_layer = sum(p.source_kind == "text_layer" for p in pages)
    return {
        "pages": len(pages),
        "text_layer_pages": text_layer,
        "ocr_pages": len(pages) - text_layer,
        "skipped_ocr_pages": ext.skipped_ocr_pages,
    }


def error_code(e: ActivityError) -> str:
    cause = e.cause
    if isinstance(cause, ApplicationError) and cause.type in KNOWN_ERRORS:
        return cause.type
    return "ingestion_failed"


@workflow.defn
class IngestDocumentWorkflow:
    @workflow.run
    async def run(self, inp: IngestInput) -> IngestOutcome:
        try:
            await workflow.execute_activity_method(
                A.mark_processing,
                inp,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=THREE,
            )
            pages = await workflow.execute_activity_method(
                A.parse_and_mask,
                inp,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=HEARTBEAT,
                retry_policy=THREE,
            )
            cls = await workflow.execute_activity_method(
                A.classify_document,
                pages,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=THREE,
            )
            ext = await workflow.execute_activity_method(
                A.extract_structured,
                args=[cls.doc_type, pages],
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=THREE,
            )
            validated = await workflow.execute_activity_method(
                A.validate_and_flag,
                args=[ext, pages, cls.patient_sex],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=ONCE,
            )
            chunks = await workflow.execute_activity_method(
                A.chunk_and_embed,
                pages,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=HEARTBEAT,
                retry_policy=THREE,
            )
            stored = await workflow.execute_activity_method(
                A.store_results,
                args=[inp, cls, validated, chunks, page_stats(pages, ext)],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=FIVE,
            )
            return IngestOutcome(status="done" if stored else "deleted")
        except ActivityError as e:
            code = error_code(e)
            await workflow.execute_activity_method(
                A.mark_failed,
                args=[inp, code],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=THREE,
            )
            return IngestOutcome(status="failed", error_code=code)
