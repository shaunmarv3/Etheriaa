"""Builds the chat stack at startup: checkpointer pool, graph dependencies, the
compiled graph and the service. The api layer may import anything; this is the
one place the pieces meet. Tests pass `overrides` (for example scripted models)
for any GraphDeps field."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import neo4j
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from redis.asyncio import Redis

from etheria.cache.json_cache import JsonCache
from etheria.core.settings import Settings
from etheria.db.session import Database
from etheria.graph.builder import build_graph, serializer
from etheria.graph.deps import GraphDeps
from etheria.graph.service import ChatService
from etheria.knowledge.conditions import ConditionExplorer
from etheria.knowledge.interactions import InteractionService
from etheria.knowledge.resolver import MedicineResolver
from etheria.llm.registry import RegistryModels
from etheria.medical_apis.base import create_http_client
from etheria.medical_apis.medlineplus import MedlinePlus
from etheria.medical_apis.pubmed import PubMed
from etheria.retrieval.embedding import BgeEmbedder
from etheria.retrieval.query_cache import CachedQueryEmbedder
from etheria.retrieval.rerank import CrossEncoderReranker
from etheria.safety.cautions import load_cautions
from etheria.safety.triage_rules import RuleMatcher


@dataclass
class ChatStack:
    service: ChatService | None
    pool: AsyncConnectionPool
    http: httpx.AsyncClient
    warmup: asyncio.Task | None = field(default=None)

    async def close(self) -> None:
        if self.warmup is not None:
            self.warmup.cancel()
        if self.service is not None:
            await self.service.drain()
        await self.pool.close()
        await self.http.aclose()


async def build_chat(
    settings: Settings,
    db: Database,
    redis: Redis,
    driver: neo4j.AsyncDriver,
    overrides: dict[str, Any] | None = None,
) -> ChatStack:
    overrides = dict(overrides or {})
    pool = AsyncConnectionPool(
        settings.database_url,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open(wait=False)  # connects lazily: the app starts even if Postgres is down
    http = create_http_client()
    stack = ChatStack(service=None, pool=pool, http=http)
    if "models" not in overrides and settings.deepseek_api_key is None:
        return stack  # no model key: chat answers 503, everything else works

    cache = JsonCache(redis)
    embedder = BgeEmbedder(settings.embedding_model)
    reranker = CrossEncoderReranker()
    ncbi = settings.ncbi_api_key.get_secret_value() if settings.ncbi_api_key else None
    resolver = MedicineResolver(db, driver)
    deps = GraphDeps(
        db=db,
        models=RegistryModels(settings),
        matcher=RuleMatcher.load(),
        cautions=load_cautions(),
        explorer=ConditionExplorer(driver, cache),
        interactions=InteractionService(resolver, driver, cache),
        resolver=resolver,
        pubmed=PubMed(http, cache, ncbi),
        medlineplus=MedlinePlus(http, cache),
        query_embedder=CachedQueryEmbedder(embedder, cache),
        reranker=reranker,
        caches=[cache],
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    saver = AsyncPostgresSaver(pool, serde=serializer())
    service = ChatService(db, build_graph(deps, saver), saver, audit_models=deps.models)
    if "start_audit" not in overrides:
        deps.start_audit = service.start_audit
    stack.service = service
    if not overrides:
        # Load the local models in the background: loading on the first request
        # took 19 s (the reranker) and would exceed the 8 s tool timeout (BGE).
        stack.warmup = asyncio.create_task(_warm(embedder, reranker))
    return stack


async def _warm(embedder: BgeEmbedder, reranker: CrossEncoderReranker) -> None:
    await asyncio.to_thread(reranker.load)
    await asyncio.to_thread(embedder.load)
