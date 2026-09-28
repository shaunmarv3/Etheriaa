"""Cache-aside for public data only (spec D9, 8.3): medical API responses,
query embeddings, knowledge-graph lookups. Never answers or anything user-scoped.

Redis is an optimisation here, not a dependency: when it is down the fetch
still runs (fail open) and the failure is logged."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

import structlog
from redis.exceptions import RedisError

log = structlog.get_logger(__name__)
T = TypeVar("T")


class _Redis(Protocol):
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: str, ex: int) -> Any: ...


class JsonCache:
    def __init__(self, redis: _Redis | None, namespace: str = "cache") -> None:
        self._redis = redis
        self._namespace = namespace
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(source: str, *parts: object) -> str:
        """`cache:<source>:<digest>`. Hashing bounds the key length for long queries."""
        digest = hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()[:32]
        return f"cache:{source}:{digest}"

    async def get_or_fetch(self, key: str, ttl_s: int, fetch: Callable[[], Awaitable[T]]) -> T:
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
            except RedisError as e:
                log.warning("cache_read_failed", key=key, error=type(e).__name__)
                raw = None
            if raw is not None:
                self.hits += 1
                return json.loads(raw)
        self.misses += 1
        value = await fetch()  # errors propagate and are never cached
        if self._redis is not None:
            try:
                await self._redis.set(key, json.dumps(value), ex=ttl_s)
            except RedisError as e:
                log.warning("cache_write_failed", key=key, error=type(e).__name__)
        return value
