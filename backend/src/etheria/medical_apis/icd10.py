"""ICD-10-CM through the NLM Clinical Table Search Service (ported from v1
`icd_lookup.py`). No key. Cached 30 days. The response is a JSON array:
[total, codes, extra, [[code, name], ...]]."""

import httpx
from pydantic import BaseModel

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.base import DAY, ApiClient

SEARCH_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"


class Icd10Code(BaseModel):
    code: str
    name: str


class Icd10:
    def __init__(self, http: httpx.AsyncClient, cache: JsonCache) -> None:
        self.api = ApiClient(http, cache, source="icd10", per_second=10, ttl_s=30 * DAY)

    async def _query(self, sf: str, terms: str, k: int) -> list[Icd10Code]:
        async def fetch() -> list[list[str]]:
            data = await self.api.get_json(
                SEARCH_URL, params={"sf": sf, "df": "code,name", "terms": terms, "maxList": k}
            )
            return [[row[0], row[1]] for row in (data[3] or [])]

        rows = await self.api.cached((sf, terms.strip().lower(), k), fetch)
        return [Icd10Code(code=c, name=n) for c, n in rows]

    async def lookup(self, code: str) -> Icd10Code | None:
        """The exact code, or None. A prefix match is never returned as the code."""
        code = code.strip().upper()
        for hit in await self._query("code", code, 10):
            if hit.code.upper() == code:
                return hit
        return None

    async def search(self, term: str, k: int = 10) -> list[Icd10Code]:
        return await self._query("code,name", term, max(1, min(k, 50)))
