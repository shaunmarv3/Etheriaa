import time
from pathlib import Path

import httpx
import pytest

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.base import ApiClient, MedicalApiError
from etheria.medical_apis.bioportal import BioPortal
from etheria.medical_apis.icd10 import Icd10
from etheria.medical_apis.medlineplus import MedlinePlus
from etheria.medical_apis.pubmed import PubMed
from etheria.medical_apis.rxnav import RxNav


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


# --- clients, parsed from real responses captured in tests/fixtures/medical_apis ---

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "medical_apis"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class Recorder:
    """A MockTransport handler that serves fixtures by URL path and records requests."""

    def __init__(self, routes: dict[str, bytes]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        for suffix, body in self.routes.items():
            if req.url.path.endswith(suffix):
                return httpx.Response(200, content=body)
        return httpx.Response(404)


def http_for(rec: Recorder) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(rec))


async def test_pubmed_search_articles_parses_abstracts() -> None:
    rec = Recorder(
        {
            "esearch.fcgi": fixture("pubmed_esearch.json"),
            "efetch.fcgi": fixture("pubmed_efetch.xml"),
        }
    )
    pubmed = PubMed(http_for(rec), JsonCache(None), api_key="k")
    articles = await pubmed.search_articles("dengue fever", k=2)
    assert [a.pmid for a in articles] == ["42801955", "42801443"]
    assert articles[0].title.startswith("Assessment of the persistence")
    assert articles[0].abstract and articles[0].year == "2026"
    assert all(r.url.params["api_key"] == "k" for r in rec.requests)
    assert rec.requests[0].url.params["retmax"] == "2"


async def test_pubmed_search_with_no_hits_skips_efetch() -> None:
    empty = b'{"esearchresult": {"idlist": []}}'
    rec = Recorder({"esearch.fcgi": empty})
    assert await PubMed(http_for(rec), JsonCache(None)).search_articles("zzz") == []
    assert len(rec.requests) == 1


async def test_medlineplus_strips_highlight_markup() -> None:
    rec = Recorder({"/ws/query": fixture("medlineplus.xml")})
    topics = await MedlinePlus(http_for(rec), JsonCache(None)).search("dengue", k=2)
    assert topics[0].title == "Dengue"
    assert topics[0].url == "https://medlineplus.gov/dengue.html"
    assert topics[0].summary.startswith("What is dengue?")
    assert "<" not in topics[0].summary and "qt0" not in topics[0].summary


async def test_icd10_lookup_exact_code() -> None:
    rec = Recorder({"/search": fixture("icd10_code.json")})
    code = await Icd10(http_for(rec), JsonCache(None)).lookup("a90")
    assert code is not None and code.code == "A90"
    assert code.name == "Dengue fever [classical dengue]"


async def test_icd10_lookup_unknown_code_is_none() -> None:
    rec = Recorder({"/search": fixture("icd10_search.json")})  # A90, A91 but not A92
    assert await Icd10(http_for(rec), JsonCache(None)).lookup("A92") is None


async def test_icd10_search() -> None:
    rec = Recorder({"/search": fixture("icd10_search.json")})
    codes = await Icd10(http_for(rec), JsonCache(None)).search("dengue")
    assert [c.code for c in codes] == ["A90", "A91"]


async def test_bioportal_exact_concept_with_snomed_and_cui() -> None:
    rec = Recorder({"/search": fixture("bioportal.json")})
    concept = await BioPortal(http_for(rec), JsonCache(None), api_key="k").find_concept(
        "dengue fever"
    )
    assert concept is not None
    assert (concept.pref_label, concept.snomed, concept.cui) == ("Dengue", "38362002", "C0011311")
    req = rec.requests[0]
    assert req.headers["Authorization"] == "apikey token=k"
    assert req.url.params["require_exact_match"] == "true"


async def test_bioportal_no_exact_match_is_none() -> None:
    rec = Recorder({"/search": fixture("bioportal_empty.json")})
    bp = BioPortal(http_for(rec), JsonCache(None), api_key="k")
    assert await bp.find_concept("loose motions") is None


async def test_rxnav_rxcui_and_not_found() -> None:
    rec = Recorder({"/rxcui.json": fixture("rxnav.json")})
    assert await RxNav(http_for(rec), JsonCache(None)).rxcui("acetaminophen") == "161"
    rec = Recorder({"/rxcui.json": fixture("rxnav_none.json")})
    assert await RxNav(http_for(rec), JsonCache(None)).rxcui("notadrug") is None
