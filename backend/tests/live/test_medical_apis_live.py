"""One real call per client. Skipped unless `pytest --live` (network, keys)."""

from collections.abc import AsyncIterator

import httpx
import pytest
from dotenv import dotenv_values

from etheria.cache.json_cache import JsonCache
from etheria.core.settings import BACKEND_DIR
from etheria.medical_apis.base import create_http_client
from etheria.medical_apis.bioportal import BioPortal
from etheria.medical_apis.icd10 import Icd10
from etheria.medical_apis.medlineplus import MedlinePlus
from etheria.medical_apis.pubmed import PubMed
from etheria.medical_apis.rxnav import RxNav

ENV = dotenv_values(BACKEND_DIR / ".env")
NO_CACHE = JsonCache(None)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with create_http_client() as c:
        yield c


async def test_pubmed(http: httpx.AsyncClient) -> None:
    articles = await PubMed(http, NO_CACHE, ENV.get("NCBI_API_KEY")).search_articles("dengue", 3)
    assert articles and all(a.abstract for a in articles)


async def test_medlineplus(http: httpx.AsyncClient) -> None:
    topics = await MedlinePlus(http, NO_CACHE).search("anemia")
    assert topics and topics[0].url.startswith("https://medlineplus.gov/")


async def test_icd10(http: httpx.AsyncClient) -> None:
    code = await Icd10(http, NO_CACHE).lookup("E11.9")
    assert code is not None and "diabetes" in code.name.lower()


async def test_bioportal(http: httpx.AsyncClient) -> None:
    key = ENV.get("BIOPORTAL_API_KEY")
    if not key:
        pytest.skip("BIOPORTAL_API_KEY not set")
    concept = await BioPortal(http, NO_CACHE, key).find_concept("Diarrhoea")
    assert concept is not None and concept.snomed == "62315008"


async def test_rxnav(http: httpx.AsyncClient) -> None:
    assert await RxNav(http, NO_CACHE).rxcui("acetaminophen") == "161"
