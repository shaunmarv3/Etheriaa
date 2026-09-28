"""Everything the chat graph's nodes and tools use, bundled once at startup.
Nodes are closures over a `GraphDeps`, so tests swap any service for a fake
(the models above all) without touching the graph."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from etheria.cache.json_cache import JsonCache
from etheria.db.session import Database
from etheria.llm.registry import NodeName
from etheria.retrieval.rerank import Reranker
from etheria.safety.cautions import CautionTable
from etheria.safety.triage_rules import RuleMatcher


class ModelFactory(Protocol):
    def structured(self, node: NodeName, schema: type[BaseModel]) -> Runnable[Any, Any]: ...
    def chat(self, node: NodeName) -> BaseChatModel: ...


class QueryEmbedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class AuditJob:
    """What the post-hoc audit needs; handed to `start_audit` after finalize persists."""

    user_id: UUID
    message_id: UUID
    created_at: datetime
    question: str
    reply: str
    triage_level: str
    evidence: list[str]


@dataclass
class GraphDeps:
    db: Database
    models: ModelFactory
    matcher: RuleMatcher
    cautions: CautionTable
    explorer: Any  # knowledge.conditions.ConditionExplorer
    interactions: Any  # knowledge.interactions.InteractionService
    resolver: Any  # knowledge.resolver.MedicineResolver
    pubmed: Any  # medical_apis.pubmed.PubMed
    medlineplus: Any  # medical_apis.medlineplus.MedlinePlus
    query_embedder: QueryEmbedder
    reranker: Reranker | None = None
    caches: list[JsonCache] = field(default_factory=list)  # for the trace's cache_hit
    start_audit: Callable[[AuditJob], None] | None = None
    tool_timeout_s: float = 8.0
    agent_timeout_s: float = 25.0
    evidence_budget_tokens: int = 6000

    def cache_hits(self) -> int:
        return sum(c.hits for c in self.caches)
