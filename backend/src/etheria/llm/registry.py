"""The one place that maps a node to a model (spec 4.9). M3 adds the ingestion
nodes; M4 adds the chat-graph nodes to the same table."""

from collections.abc import Callable
from typing import Any, Literal, get_args

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel

from etheria.core.settings import Settings

NodeName = Literal[
    "classify_document",
    "extract_lab_report",
    "extract_prescription",
    "extract_discharge_summary",
    "extract_imaging_report",
]

MODEL_FOR_NODE: dict[NodeName, str] = {node: "deepseek-flash" for node in get_args(NodeName)}

StructuredFactory = Callable[[NodeName, type[BaseModel]], Runnable[Any, Any]]


def chat_model(node: NodeName, settings: Settings) -> BaseChatModel:
    return ChatDeepSeek(
        model=MODEL_FOR_NODE[node],
        api_key=settings.deepseek_api_key,
        temperature=0,
        # deepseek-flash thinks by default; structured and tool nodes run without it (M0).
        extra_body={"thinking": {"type": "disabled"}},
        # Retries belong to the caller (Temporal's retry policy), not the client.
        max_retries=0,
        timeout=60,
    )


def structured_factory(settings: Settings) -> StructuredFactory:
    """`make(node, Schema)` -> a runnable returning a Schema instance
    (function calling scored 10/10 in M0)."""

    def make(node: NodeName, schema: type[BaseModel]) -> Runnable[Any, Any]:
        return chat_model(node, settings).with_structured_output(schema, method="function_calling")

    return make
