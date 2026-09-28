"""The Temporal client shared by the api (starts workflows, readiness probe) and
the worker. Both sides must use the same data converter: the pydantic one, so
activity inputs and outputs round-trip as our models."""

from uuid import UUID

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from etheria.core.settings import Settings

TASK_QUEUE = "ingestion"


async def connect(settings: Settings) -> Client:
    return await Client.connect(settings.temporal_address, data_converter=pydantic_data_converter)


def workflow_id(document_id: UUID) -> str:
    return f"ingest-{document_id}"
