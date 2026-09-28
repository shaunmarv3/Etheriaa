"""SNOMED CT concept and UMLS CUI through BioPortal (ported from v1 `umls_client.py`).

Exact matches only (prefLabel or synonym). The fuzzy top hit for "dengue fever"
is "Dengue hemorrhagic fever", and a wrong code is worse than no code. Cached 30 days."""

import httpx
from pydantic import BaseModel

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.base import DAY, ApiClient

SEARCH_URL = "https://data.bioontology.org/search"


class Concept(BaseModel):
    pref_label: str
    snomed: str | None
    cui: str | None


class BioPortal:
    def __init__(self, http: httpx.AsyncClient, cache: JsonCache, api_key: str) -> None:
        self.api = ApiClient(http, cache, source="bioportal", per_second=5, ttl_s=30 * DAY)
        self._headers = {"Authorization": f"apikey token={api_key}"}

    async def find_concept(self, term: str) -> Concept | None:
        async def fetch() -> dict | None:
            data = await self.api.get_json(
                SEARCH_URL,
                params={
                    "q": term,
                    "ontologies": "SNOMEDCT",
                    "include": "prefLabel,synonym,cui,semanticType",
                    "require_exact_match": "true",
                    "pagesize": 3,
                    "display_links": "false",
                    "display_context": "false",
                },
                headers=self._headers,
            )
            hits = data.get("collection") or []
            if not hits:
                return None
            top = hits[0]
            snomed = top.get("@id", "").rsplit("/", 1)[-1]
            cuis = top.get("cui") or []
            return Concept(
                pref_label=top.get("prefLabel", term),
                snomed=snomed if snomed.isdigit() else None,
                cui=cuis[0] if cuis else None,
            ).model_dump()

        row = await self.api.cached(("concept", term.strip().lower()), fetch)
        return Concept(**row) if row else None
