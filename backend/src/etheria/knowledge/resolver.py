"""Medicine resolution (spec 6.3): a brand or generic name -> DDInter drugs.

name -> itself an ingredient / synonym / drug? -> exact brand -> trigram brand
(word similarity >= 0.45; the best ingredient set must lead the best
*different* set by 0.1, otherwise ambiguous) -> ingredients -> spelling, salt
and synonym canonicalisation -> Drug nodes. Anything not matched is reported,
never guessed. The lead rule compares ingredient sets, not brand names:
"Dolo 650" and "Dolo 500" are two strengths of one product, not an ambiguity.

Word similarity (not plain similarity) scores the query against the best
matching extent of the brand name, so a short query such as "Brufen" scores
1.0 against "Brufen 400 Tablet" instead of 0.39 (spec 4.5, M2 gap). When the
close candidates differ (Brufen vs Brufen MR, which adds tizanidine), the
result stays ambiguous, but the ingredients every candidate shares are
returned so interaction checks still cover them.

`variants` says what each product behind a name contains, so the answer can
name them (spec 4.5): for an ambiguous name, one entry per ingredient set among
the close candidates (Brufen vs Brufen MR, which adds tizanidine); for a
matched brand, the other products sold under the same name that contain
something else (Telma 40 matched, but Telma H adds hydrochlorothiazide), because
a user who types "Telma 40" may be holding a Telma H strip."""

import re
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

MAX_VARIANTS = 5
Candidate = tuple[str, float, tuple[str, ...]]  # brand, similarity, ingredient set

# Words that name a dosage form or release type, not a different product.
_FORM_WORDS = frozenset(
    "tablet tablets tab capsule capsules cap syrup suspension injection drops soft gelatin "
    "er sr xr cr dt oral solution".split()
)
_TOKEN = re.compile(r"[^\w./]+")


class BrandVariant(BaseModel):
    brands: list[str]  # products with this ingredient set (a few, as named in the table)
    ingredients: list[str]  # as the brand table lists them, not mapped to Drug nodes


class Resolution(BaseModel):
    query: str
    status: Literal["resolved", "ambiguous", "unresolved"]
    matched_brand: str | None = None
    ingredients: list[str] = []  # Drug node names (DDInter or curated)
    unresolved_ingredients: list[str] = []
    candidates: list[str] = []  # the close brands, when ambiguous
    shared_ingredients: list[str] = []  # Drug names every close candidate contains
    # ambiguous: one entry per ingredient set among the candidates; resolved brand:
    # other products under the same name with different ingredients
    variants: list[BrandVariant] = []
    more_variants: int = 0  # ingredient sets left out of `variants`


def _tokens(name: str) -> list[str]:
    return [t for t in _TOKEN.split(normalise_name(name)) if t]


def group_variants(cands: Sequence[tuple[str, tuple[str, ...]]]) -> list[BrandVariant]:
    """One entry per ingredient set, in the order the sets first appear."""
    groups: dict[tuple[str, ...], list[str]] = {}
    for name, ingredients in cands:
        names = groups.setdefault(ingredients, [])
        if name not in names:
            names.append(name)
    return [BrandVariant(brands=names[:3], ingredients=list(s)) for s, names in groups.items()]


def family_variants(
    query: str, matched: tuple[str, ...], family: Sequence[tuple[str, tuple[str, ...]]]
) -> tuple[list[BrandVariant], int]:
    """Products under the same name with an ingredient set other than `matched`,
    one per set, the plainest name first: fewest words that are neither in the
    query nor a dosage form ("Telma H Tablet" before "Telma-AM H 40 Tablet")."""
    asked = set(_tokens(query))

    def extra(name: str) -> int:
        return sum(1 for t in _tokens(name) if t not in asked and t not in _FORM_WORDS)

    best: dict[tuple[str, ...], str] = {}
    for name, ingredients in sorted(family, key=lambda f: (extra(f[0]), len(f[0]), f[0])):
        if ingredients != matched and ingredients not in best:
            best[ingredients] = name
    variants = [BrandVariant(brands=[n], ingredients=list(s)) for s, n in best.items()]
    return variants[:MAX_VARIANTS], max(0, len(variants) - MAX_VARIANTS)


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
            # `<%` uses the GIN trigram index; the threshold is local to this transaction.
            await s.execute(
                text("SELECT set_config('pg_trgm.word_similarity_threshold', :t, true)"),
                {"t": str(MIN_SIMILARITY)},
            )
            rows = await s.execute(
                text(
                    "SELECT name, word_similarity(:q, name) AS sim, ingredients "
                    "FROM medicine_brands WHERE :q <% name "
                    "ORDER BY sim DESC, similarity(name, :q) DESC, name LIMIT 20"
                ),
                {"q": q},
            )
            return [(n, float(sim), tuple(sorted(i))) for n, sim, i in rows]

    async def _family(self, brand: str) -> list[tuple[str, tuple[str, ...]]]:
        """Every product whose name starts with the brand's first word as a whole
        word ("Telma 40 Tablet" -> Telma H, Telma-AM, not Telmax)."""
        word = _tokens(brand)[0] if _tokens(brand) else ""
        if len(word) < 3:
            return []
        async with self._db.system() as s:
            rows = await s.execute(
                text(
                    "SELECT name, ingredients FROM medicine_brands "
                    "WHERE name ILIKE :space OR name ILIKE :dash OR lower(name) = :w LIMIT 500"
                ),
                {"space": f"{word} %", "dash": f"{word}-%", "w": word},
            )
            return [(n, tuple(sorted(i))) for n, i in rows]

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
            close = [(n, i) for n, sim, i in cands if sim >= cands[0][1] - MIN_LEAD]
            common = set.intersection(*(set(i) for _, i in close))
            mapped = await self._canonical(sorted(common)) if common else {}
            variants = group_variants(close)
            return Resolution(
                query=name,
                status="ambiguous",
                candidates=[n for n, _ in close][:5],
                shared_ingredients=sorted({d for d in mapped.values() if d}),
                variants=variants[:MAX_VARIANTS],
                more_variants=max(0, len(variants) - MAX_VARIANTS),
            )

        brand, ingredients = picked
        mapped = await self._canonical(ingredients) if ingredients else {}
        variants, more = family_variants(name, ingredients, await self._family(brand))
        return Resolution(
            query=name,
            status="resolved",
            matched_brand=brand,
            ingredients=sorted({d for d in mapped.values() if d}),
            unresolved_ingredients=sorted(i for i, d in mapped.items() if d is None),
            variants=variants,
            more_variants=more,
        )
