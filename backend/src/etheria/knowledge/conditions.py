"""Symptom matching and condition exploration (spec 4.5 `explore_conditions`).

A user's words are matched to curated symptoms exactly first (name or any lay
term, case-insensitive: "loose motions" -> diarrhoea), then through the
full-text index, requiring every word to match. Conditions are ranked by
matched weight x coverage (coverage = matched weight / the condition's total
weight), then matched weight. Coverage alone over-rewards conditions with a
short symptom list (dengue fell to third for fever + body ache + pain behind
the eyes); the matched weight alone over-rewards long lists (headache alone
ranked meningitis second). The product drops a condition whose cardinal
symptoms are absent and keeps one whose key symptoms are all present
(spec 4.5, M2 gap).
This is background for the answer, not a diagnosis (spec 4.6)."""

import re

import neo4j
from pydantic import BaseModel

from etheria.cache.json_cache import JsonCache
from etheria.knowledge.text import normalise_name

GRAPH_TTL_S = 24 * 3600  # knowledge-graph lookups (spec 8.3)

_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\/]|&&|\|\|)')


class ConditionHit(BaseModel):
    icd10: str
    name: str
    score: float
    coverage: float = 0.0
    matched_symptoms: list[str]
    first_line_classes: list[str]
    self_care: list[str]
    red_flags: list[str]


class Exploration(BaseModel):
    matched: dict[str, str]  # user term -> symptom code
    unmatched: list[str]
    conditions: list[ConditionHit]


def _all_words_query(term: str) -> str | None:
    words = [_LUCENE_SPECIAL.sub(r"\\1", w) for w in normalise_name(term).split()]
    return " AND ".join(words) if words else None


class ConditionExplorer:
    def __init__(self, driver: neo4j.AsyncDriver, cache: JsonCache | None = None) -> None:
        self._driver = driver
        self._cache = cache

    async def match_symptoms(self, terms: list[str]) -> dict[str, str | None]:
        norm = {t: normalise_name(t) for t in terms}
        records, _, _ = await self._driver.execute_query(
            "UNWIND $terms AS t MATCH (s:Symptom) WHERE t IN s.terms RETURN t, s.code",
            terms=sorted(set(norm.values())),
        )
        exact = {t: code for t, code in records}
        out: dict[str, str | None] = {}
        for term, n in norm.items():
            if n in exact:
                out[term] = exact[n]
                continue
            query = _all_words_query(term)
            out[term] = None
            if query:
                hits, _, _ = await self._driver.execute_query(
                    "CALL db.index.fulltext.queryNodes('symptom_text', $q) YIELD node, score "
                    "RETURN node.code ORDER BY score DESC LIMIT 1",
                    q=query,
                )
                out[term] = hits[0][0] if hits else None
        return out

    async def explore(self, symptoms: list[str], k: int = 5) -> Exploration:
        if self._cache is None:
            return await self._explore(symptoms, k)
        key = JsonCache.key("kg", "explore", sorted(normalise_name(x) for x in symptoms), k)

        async def fetch() -> dict:
            return (await self._explore(symptoms, k)).model_dump()

        return Exploration(**await self._cache.get_or_fetch(key, GRAPH_TTL_S, fetch))

    async def _explore(self, symptoms: list[str], k: int) -> Exploration:
        matched = await self.match_symptoms(symptoms)
        codes = sorted({c for c in matched.values() if c})
        records, _, _ = await self._driver.execute_query(
            "MATCH (s:Symptom)-[r:ASSOCIATED_WITH]->(c:Condition) WHERE s.code IN $codes "
            "WITH c, sum(r.weight) AS score, collect(s.name) AS matched "
            "MATCH (:Symptom)-[w:ASSOCIATED_WITH]->(c) "
            "WITH c, score, matched, score / sum(w.weight) AS coverage "
            "ORDER BY score * coverage DESC, score DESC, c.name LIMIT $k "
            "OPTIONAL MATCH (c)-[:FIRST_LINE]->(dc:DrugClass) "
            "RETURN c.icd10 AS icd10, c.name AS name, score, coverage, matched, "
            "collect(dc.label) AS classes, c.self_care AS self_care, c.red_flags AS red_flags "
            "ORDER BY score * coverage DESC, score DESC, name",
            codes=codes,
            k=k,
        )
        return Exploration(
            matched={t: c for t, c in matched.items() if c},
            unmatched=[t for t, c in matched.items() if not c],
            conditions=[
                ConditionHit(
                    icd10=r["icd10"],
                    name=r["name"],
                    score=r["score"],
                    coverage=r["coverage"],
                    matched_symptoms=r["matched"],
                    first_line_classes=r["classes"],
                    self_care=r["self_care"] or [],
                    red_flags=r["red_flags"] or [],
                )
                for r in records
            ],
        )
