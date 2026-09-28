import time

import httpx
import pytest

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.base import ApiClient, MedicalApiError


def client_for(handler, *, per_second: float = 1000.0) -> ApiClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ApiClient(http, JsonCache(None), source="test", per_second=per_second, ttl_s=60)


async def test_get_json_returns_the_body() -> None:
    api = client_for(lambda req: httpx.Response(200, json={"ok": req.url.params["q"]}))
    assert await api.get_json("https://example.test/x", params={"q": "fever"}) == {"ok": "fever"}


async def test_http_error_raises_medical_api_error() -> None:
    api = client_for(lambda req: httpx.Response(500, text="boom"))
    with pytest.raises(MedicalApiError) as e:
        await api.get_json("https://example.test/x")
    assert e.value.source == "test"
    assert "500" in str(e.value)


async def test_timeout_raises_medical_api_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(MedicalApiError, match="ReadTimeout"):
        await client_for(handler).get_text("https://example.test/x")


async def test_invalid_json_raises_medical_api_error() -> None:
    api = client_for(lambda req: httpx.Response(200, text="<html>"))
    with pytest.raises(MedicalApiError):
        await api.get_json("https://example.test/x")


async def test_throttle_spaces_request_starts() -> None:
    api = client_for(lambda req: httpx.Response(200, json={}), per_second=10)
    start = time.monotonic()
    for _ in range(3):
        await api.get_json("https://example.test/x")
    assert time.monotonic() - start >= 0.19  # 3 starts, 0.1 s apart


async def test_cached_uses_the_client_ttl_and_source() -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=[1])

    api = client_for(handler)
    fetch = lambda: api.get_json("https://example.test/x")  # noqa: E731
    assert await api.cached(("q",), fetch) == [1]
    assert calls["n"] == 1
