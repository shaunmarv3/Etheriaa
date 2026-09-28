"""Cached query embeddings (spec 8.3: 7 days, key = model + SHA-256 of the text).
A query embedding is public (it is a function of the text only), so it may be
cached; the chunks it retrieves are user-scoped and never are. BGE runs in a
worker thread so the event loop keeps streaming."""

import asyncio
import hashlib
from typing import Protocol

from etheria.cache.json_cache import JsonCache

TTL_S = 7 * 24 * 3600


class _QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class CachedQueryEmbedder:
    def __init__(self, embedder: _QueryEmbedder, cache: JsonCache) -> None:
        self._embedder = embedder
        self._cache = cache
        self._model = getattr(embedder, "model_name", type(embedder).__name__)

    async def embed_query(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).hexdigest()
        key = JsonCache.key("embedding", self._model, digest)

        async def fetch() -> list[float]:
            return await asyncio.to_thread(self._embedder.embed_query, text)

        return await self._cache.get_or_fetch(key, TTL_S, fetch)
