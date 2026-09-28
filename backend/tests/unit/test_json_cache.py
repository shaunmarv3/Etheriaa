import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from etheria.cache.json_cache import JsonCache


class MemoryRedis:
    """The two Redis calls JsonCache makes, backed by a dict."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> bytes | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value.encode()
        self.ttls[key] = ex


class DownRedis:
    async def get(self, key: str) -> bytes | None:
        raise RedisConnectionError("down")

    async def set(self, key: str, value: str, ex: int) -> None:
        raise RedisConnectionError("down")


def counting_fetch(value: object):
    calls = {"n": 0}

    async def fetch() -> object:
        calls["n"] += 1
        return value

    return fetch, calls


async def test_miss_then_hit_fetches_once() -> None:
    redis = MemoryRedis()
    cache = JsonCache(redis)
    fetch, calls = counting_fetch({"a": [1, 2]})
    key = JsonCache.key("pubmed", "fever", 5)
    assert await cache.get_or_fetch(key, 60, fetch) == {"a": [1, 2]}
    assert await cache.get_or_fetch(key, 60, fetch) == {"a": [1, 2]}
    assert calls["n"] == 1
    assert (cache.misses, cache.hits) == (1, 1)
    assert redis.ttls[key] == 60


async def test_empty_results_are_cached_too() -> None:
    cache = JsonCache(MemoryRedis())
    fetch, calls = counting_fetch([])
    key = JsonCache.key("icd10", "nothing")
    await cache.get_or_fetch(key, 60, fetch)
    await cache.get_or_fetch(key, 60, fetch)
    assert calls["n"] == 1


async def test_redis_down_fails_open() -> None:
    cache = JsonCache(DownRedis())
    fetch, calls = counting_fetch("value")
    assert await cache.get_or_fetch(JsonCache.key("x", 1), 60, fetch) == "value"
    assert calls["n"] == 1


async def test_no_redis_means_no_cache() -> None:
    cache = JsonCache(None)
    fetch, calls = counting_fetch(1)
    await cache.get_or_fetch("k", 60, fetch)
    await cache.get_or_fetch("k", 60, fetch)
    assert calls["n"] == 2


async def test_fetch_error_propagates_and_nothing_is_cached() -> None:
    redis = MemoryRedis()
    cache = JsonCache(redis)

    async def boom() -> object:
        raise RuntimeError("upstream down")

    with pytest.raises(RuntimeError):
        await cache.get_or_fetch("k", 60, boom)
    assert redis.data == {}


def test_keys_are_namespaced_bounded_and_stable() -> None:
    k1 = JsonCache.key("pubmed", "a very long query " * 50, 5)
    assert k1 == JsonCache.key("pubmed", "a very long query " * 50, 5)
    assert k1.startswith("cache:pubmed:")
    assert len(k1) < 64
    assert k1 != JsonCache.key("pubmed", "a very long query " * 50, 6)
    assert k1 != JsonCache.key("medlineplus", "a very long query " * 50, 5)
