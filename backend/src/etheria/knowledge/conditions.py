"""Symptom matching and condition exploration (spec 4.5 `explore_conditions`).

A user's words are matched to curated symptoms exactly first (name or any lay
term, case-insensitive: "loose motions" -> diarrhoea), then through the
full-text index, requiring every word to match. Conditions are ranked by the
summed weights of the matched symptoms. This is background for the answer,
not a diagnosis (spec 4.6)."""

import re

import neo4j
from pydantic import BaseModel

from etheria.knowledge.text import normalise_name

_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\/]|&&|\|\|)')


class ConditionHit(BaseModel):
    icd10: str
    name: str
    score: float
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
    def __init__(self, driver: neo4j.AsyncDriver) -> None:
        self._driver = driver

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
        matched = await self.match_symptoms(symptoms)
        codes = sorted({c for c in matched.values() if c})
        records, _, _ = await self._driver.execute_query(
            "MATCH (s:Symptom)-[r:ASSOCIATED_WITH]->(c:Condition) WHERE s.code IN $codes "
            "WITH c, sum(r.weight) AS score, collect(s.name) AS matched "
            "ORDER BY score DESC, c.name LIMIT $k "
            "OPTIONAL MATCH (c)-[:FIRST_LINE]->(dc:DrugClass) "
            "RETURN c.icd10 AS icd10, c.name AS name, score, matched, "
            "collect(dc.label) AS classes, c.self_care AS self_care, c.red_flags AS red_flags "
            "ORDER BY score DESC, name",
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
                    matched_symptoms=r["matched"],
                    first_line_classes=r["classes"],
                    self_care=r["self_care"] or [],
                    red_flags=r["red_flags"] or [],
                )
                for r in records
            ],
        )
