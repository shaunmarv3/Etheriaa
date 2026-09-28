"""MedlinePlus health topics (ported from v1 `medlineplus_client.py`): plain-language
summaries. No key. NLM asks for at most 85 requests a minute. Cached 7 days."""

import html
import re
import xml.etree.ElementTree as ET

import httpx
from pydantic import BaseModel

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.base import DAY, ApiClient, MedicalApiError

SEARCH_URL = "https://wsearch.nlm.nih.gov/ws/query"
_TAG = re.compile(r"<[^>]+>")


class HealthTopic(BaseModel):
    title: str
    url: str
    summary: str


class MedlinePlus:
    def __init__(self, http: httpx.AsyncClient, cache: JsonCache) -> None:
        self.api = ApiClient(http, cache, source="medlineplus", per_second=1, ttl_s=7 * DAY)

    async def search(self, term: str, k: int = 3) -> list[HealthTopic]:
        k = max(1, min(k, 10))

        async def fetch() -> list[dict]:
            xml = await self.api.get_text(
                SEARCH_URL, params={"db": "healthTopics", "term": term, "retmax": k}
            )
            return [t.model_dump() for t in parse_topics(xml)]

        rows = await self.api.cached(("search", term.strip().lower(), k), fetch)
        return [HealthTopic(**r) for r in rows]


def clean(fragment: str) -> str:
    """Search results carry HTML (including highlight spans) escaped inside XML."""
    text = html.unescape(_TAG.sub(" ", html.unescape(fragment)))
    text = _TAG.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([?.,;:!])", r"\1", text)


def parse_topics(xml: str) -> list[HealthTopic]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise MedicalApiError("medlineplus", "malformed XML") from e
    topics = []
    for doc in root.iter("document"):
        fields: dict[str, str] = {}
        for c in doc.findall("content"):
            name = c.get("name", "")
            if name not in fields and c.text:
                fields[name] = c.text
        if "FullSummary" in fields:
            topics.append(
                HealthTopic(
                    title=clean(fields.get("title", "")),
                    url=doc.get("url", ""),
                    summary=clean(fields["FullSummary"]),
                )
            )
    return topics
