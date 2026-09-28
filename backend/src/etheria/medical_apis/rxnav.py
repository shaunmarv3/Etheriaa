"""RxNav name normalisation (ported from v1 `rxnorm_client.py`, `get_rxcui` only).

The RxNav drug-interaction API was retired on 2024-01-02; interactions come
from DDInter (spec 3.4). NLM allows 20 requests/s. Cached 30 days."""

import httpx

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.base import DAY, ApiClient

RXCUI_URL = "https://rxnav.nlm.nih.gov/REST/rxcui.json"


class RxNav:
    def __init__(self, http: httpx.AsyncClient, cache: JsonCache) -> None:
        self.api = ApiClient(http, cache, source="rxnav", per_second=15, ttl_s=30 * DAY)

    async def rxcui(self, name: str) -> str | None:
        """search=2: exact then normalised match (never an approximate match)."""

        async def fetch() -> str | None:
            data = await self.api.get_json(RXCUI_URL, params={"name": name, "search": 2})
            ids = data.get("idGroup", {}).get("rxnormId") or []
            return ids[0] if ids else None

        return await self.api.cached(("rxcui", name.strip().lower()), fetch)
