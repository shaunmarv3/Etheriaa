"""Medicine resolution (spec 6.3): a brand or generic name -> DDInter drugs.

name -> itself an ingredient / synonym / drug? -> exact brand -> trigram brand
(similarity >= 0.45; the best ingredient set must lead the best *different*
set by 0.1, otherwise ambiguous) -> ingredients -> spelling, salt and synonym
canonicalisation -> Drug nodes. Anything not matched is reported, never guessed.
The lead rule compares ingredient sets, not brand names: "Dolo 650" and
"Dolo 500" are two strengths of one product, not an ambiguity."""

from collections.abc import Sequence
from typing import Literal

import neo4j
from pydantic import BaseModel
from sqlalchemy import text

from etheria.db.session import Database
from etheria.knowledge.text import ingredient_candidates, normalise_name

MIN_SIMILARITY = 0.45
MIN_LEAD = 0.1
AMBIGUOUS = "ambiguous"
NO_MATCH = "none"

Candidate = tuple[str, float, tuple[str, ...]]  # brand, similarity, ingredient set


class Resolution(BaseModel):
    query: str
    status: Literal["resolved", "ambiguous", "unresolved"]
    matched_brand: str | None = None
    ingredients: list[str] = []  # Drug node names (DDInter or curated)
    unresolved_ingredients: list[str] = []
    candidates: list[str] = []  # the close brands, when ambiguous


def pick_candidate(
    cands: Sequence[Candidate],
) -> tuple[str, tuple[str, ...]] | Literal["ambiguous", "none"]:
    best: dict[tuple[str, ...], tuple[float, str]] = {}
    for name, sim, ingredients in cands:
        if sim >= MIN_SIMILARITY and (ingredients not in best or sim > best[ingredients][0]):
            best[ingredients] = (sim, name)
    if not best:
        return NO_MATCH
    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)
    (top_set, (top_sim, top_name)), rest = ranked[0], ranked[1:]
    if rest and top_sim - rest[0][1][0] < MIN_LEAD:
        return AMBIGUOUS
    return top_name, top_set


class MedicineResolver:
    def __init__(self, db: Database, driver: neo4j.AsyncDriver) -> None:
        self._db = db
        self._driver = driver

    async def _canonical(self, ingredients: Sequence[str]) -> dict[str, str | None]:
        """ingredient -> Drug node name, trying spelling / salt variants and synonyms."""
        tries = {i: ingredient_candidates(i) for i in ingredients}
        names = sorted({c for cands in tries.values() for c in cands})
        async with self._db.system() as s:
            rows = await s.execute(
                text(
                    "SELECT lower(alias::text), canonical FROM drug_synonyms "
                    "WHERE alias = ANY(CAST(:a AS citext[]))"
                ),
                {"a": names},
            )
            synonyms = {a: normalise_name(c) for a, c in rows}
        keys = sorted({synonyms.get(c, c) for c in names})
        records, _, _ = await self._driver.execute_query(
            "UNWIND $keys AS k MATCH (d:Drug {key: k}) RETURN k, d.name", keys=keys
        )
        drug_names = {k: n for k, n in records}
        out: dict[str, str | None] = {}
        for ingredient, cands in tries.items():
            out[ingredient] = next(
                (drug_names[synonyms.get(c, c)] for c in cands if synonyms.get(c, c) in drug_names),
                None,
            )
        return out

    async def _brands(self, q: str) -> list[Candidate]:
        async with self._db.system() as s:
            exact = (
                await s.execute(
                    text("SELECT name, ingredients FROM medicine_brands WHERE lower(name) = :q"),
                    {"q": q},
                )
            ).all()
            if exact:
                return [(n, 1.0, tuple(sorted(i))) for n, i in exact]
            # `%` uses the GIN trigram index; the threshold is local to this transaction.
            await s.execute(
                text("SELECT set_config('pg_trgm.similarity_threshold', :t, true)"),
                {"t": str(MIN_SIMILARITY)},
            )
            rows = await s.execute(
                text(
                    "SELECT name, similarity(name, :q) AS sim, ingredients "
                    "FROM medicine_brands WHERE name % :q ORDER BY sim DESC, name LIMIT 20"
                ),
                {"q": q},
            )
            return [(n, float(sim), tuple(sorted(i))) for n, sim, i in rows]

    async def resolve(self, name: str) -> Resolution:
        q = normalise_name(name)
        if not q:
            return Resolution(query=name, status="unresolved")

        direct = (await self._canonical([q]))[q]
        if direct:
            return Resolution(query=name, status="resolved", ingredients=[direct])

        cands = await self._brands(q)
        picked = pick_candidate(cands)
        if picked == NO_MATCH:
            return Resolution(query=name, status="unresolved")
        if picked == AMBIGUOUS:
            close = [n for n, sim, _ in cands if sim >= cands[0][1] - MIN_LEAD]
            return Resolution(query=name, status="ambiguous", candidates=close[:5])

        brand, ingredients = picked
        mapped = await self._canonical(ingredients) if ingredients else {}
        return Resolution(
            query=name,
            status="resolved",
            matched_brand=brand,
            ingredients=sorted({d for d in mapped.values() if d}),
            unresolved_ingredients=sorted(i for i, d in mapped.items() if d is None),
        )
