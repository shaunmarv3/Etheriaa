"""Shared plumbing for the public medical APIs (ported from v1 `medical_apis/base.py`,
aiohttp -> httpx so the codebase has one HTTP client stack).

Differences from v1, on purpose:
- Failures raise `MedicalApiError` instead of returning None, so "the API is
  down" is never confused with "no result", and failures are never cached.
- The throttle waits instead of silently skipping the request.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx

from etheria.cache.json_cache import JsonCache

T = TypeVar("T")

HOUR = 3600
DAY = 24 * HOUR


class MedicalApiError(Exception):
    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"{source}: {message}")
        self.source = source


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"User-Agent": "etheria-v2 (portfolio project; synthetic data only)"},
        follow_redirects=True,
    )


class ApiClient:
    """One upstream API: throttled requests plus cache-aside with that API's TTL."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        cache: JsonCache,
        *,
        source: str,
        per_second: float,
        ttl_s: int,
    ) -> None:
        self.http = http
        self.cache = cache
        self.source = source
        self.ttl_s = ttl_s
        self._interval = 1.0 / per_second
        self._lock = asyncio.Lock()
        self._next_start = 0.0

    async def _throttle(self) -> None:
        # Space request *starts*; concurrent callers queue on the lock.
        async with self._lock:
            now = time.monotonic()
            if now < self._next_start:
                await asyncio.sleep(self._next_start - now)
            self._next_start = max(now, self._next_start) + self._interval

    async def _get(self, url: str, params: dict | None, headers: dict | None) -> httpx.Response:
        await self._throttle()
        try:
            resp = await self.http.get(url, params=params, headers=headers)
        except httpx.HTTPError as e:
            raise MedicalApiError(self.source, f"{type(e).__name__}: {e}") from e
        if resp.status_code != 200:
            raise MedicalApiError(self.source, f"HTTP {resp.status_code} from {resp.url.path}")
        return resp

    async def get_json(
        self, url: str, params: dict | None = None, headers: dict | None = None
    ) -> Any:
        resp = await self._get(url, params, headers)
        try:
            return resp.json()
        except ValueError as e:
            raise MedicalApiError(self.source, "response was not JSON") from e

    async def get_text(
        self, url: str, params: dict | None = None, headers: dict | None = None
    ) -> str:
        return (await self._get(url, params, headers)).text

    async def cached(self, key_parts: tuple, fetch: Callable[[], Awaitable[T]]) -> T:
        return await self.cache.get_or_fetch(
            JsonCache.key(self.source, *key_parts), self.ttl_s, fetch
        )
