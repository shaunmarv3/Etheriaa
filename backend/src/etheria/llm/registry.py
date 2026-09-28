"""The one place that maps a node to a model (spec 4.9). Each entry holds the
model ID, temperature, timeout and max tokens; a node that fails its eval can
switch model here without touching the graph."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, get_args

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel

from etheria.core.settings import Settings

NodeName = Literal[
    # ingestion (M3)
    "classify_document",
    "extract_lab_report",
    "extract_prescription",
    "extract_discharge_summary",
    "extract_imaging_report",
    # chat graph (M4)
    "understand",
    "summarize",
    "triage",
    "retrieval_agent",
    "generate",
    "clinical_structuring",
    "audit",
]


@dataclass(frozen=True)
class ModelSpec:
    model: str = "deepseek-flash"
    temperature: float = 0.0
    timeout_s: float = 60.0
    max_tokens: int | None = None


REGISTRY: dict[NodeName, ModelSpec] = {
    "classify_document": ModelSpec(),
    "extract_lab_report": ModelSpec(),
    "extract_prescription": ModelSpec(),
    "extract_discharge_summary": ModelSpec(),
    "extract_imaging_report": ModelSpec(),
    "understand": ModelSpec(timeout_s=20, max_tokens=700),
    "summarize": ModelSpec(timeout_s=30, max_tokens=500),
    "triage": ModelSpec(timeout_s=20, max_tokens=400),
    "retrieval_agent": ModelSpec(timeout_s=20, max_tokens=800),
    "generate": ModelSpec(temperature=0.3, timeout_s=60, max_tokens=1200),
    "clinical_structuring": ModelSpec(timeout_s=30, max_tokens=900),
    # A larger model grades the reply after it has streamed (spec 4.6, "After").
    "audit": ModelSpec(model="deepseek-v4-pro", timeout_s=90, max_tokens=900),
}
assert set(REGISTRY) == set(get_args(NodeName))

MODEL_FOR_NODE: dict[NodeName, str] = {node: spec.model for node, spec in REGISTRY.items()}

StructuredFactory = Callable[[NodeName, type[BaseModel]], Runnable[Any, Any]]


def chat_model(node: NodeName, settings: Settings) -> BaseChatModel:
    spec = REGISTRY[node]
    return ChatDeepSeek(
        model=spec.model,
        api_key=settings.deepseek_api_key,
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
        # DeepSeek models think by default; structured, tool and streamed nodes
        # run without it (M0: 10/10 structured output, 0.81 s to first token).
        extra_body={"thinking": {"type": "disabled"}},
        # Retries belong to the caller: Temporal for ingestion, the node for chat.
        max_retries=0,
        timeout=spec.timeout_s,
    )


def structured_factory(settings: Settings) -> StructuredFactory:
    """`make(node, Schema)` -> a runnable returning a Schema instance
    (function calling scored 10/10 in M0)."""

    def make(node: NodeName, schema: type[BaseModel]) -> Runnable[Any, Any]:
        return chat_model(node, settings).with_structured_output(schema, method="function_calling")

    return make


class RegistryModels:
    """The chat graph's model factory (graph/deps.py `ModelFactory`)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._structured = structured_factory(settings)

    def structured(self, node: NodeName, schema: type[BaseModel]) -> Runnable[Any, Any]:
        return self._structured(node, schema)

    def chat(self, node: NodeName) -> BaseChatModel:
        return chat_model(node, self._settings)
