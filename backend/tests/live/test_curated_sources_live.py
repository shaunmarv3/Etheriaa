"""Every curated source URL resolves (pytest --live). A dead citation is a
content bug. cdc.gov answers scripted clients with 403 (bot protection), so a
403 there is reported as unverified rather than dead."""

import asyncio

import httpx

from etheria.cache.json_cache import JsonCache
from etheria.medical_apis.icd10 import Icd10
from etheria.safety.cautions import load_cautions
from etheria.seed.curated import load_curated

BOT_BLOCKED = ("https://www.cdc.gov/",)


def _sources() -> set[str]:
    c = load_curated()
    groups = [c.symptoms, c.conditions, c.critical, c.extra_drugs]
    cautions = {r.source for r in load_cautions().rules}
    return {item.source for group in groups for item in group} | cautions


async def test_every_curated_source_resolves() -> None:
    sem = asyncio.Semaphore(6)
    headers = {"User-Agent": "Mozilla/5.0 (etheria-v2 source check)"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as http:

        async def status(url: str) -> tuple[str, int]:
            async with sem:
                return url, (await http.get(url)).status_code

        results = await asyncio.gather(*(status(u) for u in sorted(_sources())))
    dead = [(u, s) for u, s in results if s != 200 and not (s == 403 and u.startswith(BOT_BLOCKED))]
    assert dead == []


async def test_every_condition_icd10_code_exists() -> None:
    async with httpx.AsyncClient(timeout=30) as http:
        icd = Icd10(http, JsonCache(None))
        codes = [x.icd10 for x in load_curated().conditions]
        found = await asyncio.gather(*(icd.lookup(code) for code in codes))
    assert [code for code, hit in zip(codes, found, strict=True) if hit is None] == []
