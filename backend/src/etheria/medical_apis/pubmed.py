"""PubMed through NCBI E-utilities (ported from v1 `pubmed_client.py`).
eSearch -> PMIDs, eFetch -> title + abstract. NCBI allows 10 requests/s with an
API key and 3/s without. Cached 24 h (spec 8.3)."""

import xml.etree.ElementTree as ET

import httpx
from pydantic import BaseModel

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.base import DAY, ApiClient, MedicalApiError

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
MAX_K = 20


class Article(BaseModel):
    pmid: str
    title: str
    abstract: str
    year: str | None
    mesh_terms: list[str]


class PubMed:
    def __init__(
        self, http: httpx.AsyncClient, cache: JsonCache, api_key: str | None = None
    ) -> None:
        self.api = ApiClient(
            http, cache, source="pubmed", per_second=10 if api_key else 3, ttl_s=DAY
        )
        self._base = {"tool": "etheria-v2", **({"api_key": api_key} if api_key else {})}

    async def search(self, query: str, k: int = 5) -> list[str]:
        k = max(1, min(k, MAX_K))

        async def fetch() -> list[str]:
            data = await self.api.get_json(
                ESEARCH_URL,
                params={
                    **self._base,
                    "db": "pubmed",
                    "term": query,
                    "retmax": k,
                    "retmode": "json",
                },
            )
            return list(data.get("esearchresult", {}).get("idlist", []))

        return await self.api.cached(("search", query.strip().lower(), k), fetch)

    async def fetch(self, pmids: list[str]) -> list[Article]:
        if not pmids:
            return []

        async def fetch() -> list[dict]:
            xml = await self.api.get_text(
                EFETCH_URL,
                params={
                    **self._base,
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "xml",
                    "rettype": "abstract",
                },
            )
            return [a.model_dump() for a in parse_efetch(xml)]

        rows = await self.api.cached(("fetch", sorted(pmids)), fetch)
        return [Article(**r) for r in rows]

    async def search_articles(self, query: str, k: int = 5) -> list[Article]:
        return await self.fetch(await self.search(query, k))


def _text(el: ET.Element | None) -> str:
    # itertext keeps inline markup such as <i>Aedes</i> as plain text.
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def parse_efetch(xml: str) -> list[Article]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise MedicalApiError("pubmed", "eFetch returned malformed XML") from e
    articles = []
    for art in root.iter("PubmedArticle"):
        parts = []
        for ab in art.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            parts.append(f"{label}: {_text(ab)}" if label else _text(ab))
        abstract = " ".join(p for p in parts if p)
        if not abstract:
            continue  # an article without an abstract is no use as evidence
        year = art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "")[:4]
        articles.append(
            Article(
                pmid=art.findtext(".//MedlineCitation/PMID", default=""),
                title=_text(art.find(".//ArticleTitle")),
                abstract=abstract,
                year=year or None,
                mesh_terms=[
                    _text(m) for m in art.findall(".//MeshHeading/DescriptorName") if _text(m)
                ],
            )
        )
    return articles
