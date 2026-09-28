"""Phase 7: codes (spec 6.4). ICD-10 names verified against NLM Clinical
Tables; SNOMED CT and UMLS CUI from BioPortal (exact matches only); RxCUI from
RxNav. Bounded concurrency; every upstream failure is listed in the report,
never swallowed. "Missing" (no exact match) is normal and counted apart from
"failed" (the API errored)."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

import neo4j

from etheria.knowledge.text import normalise_name
from etheria.medical_apis.base import MedicalApiError
from etheria.medical_apis.bioportal import Concept
from etheria.medical_apis.icd10 import Icd10Code

T = TypeVar("T")
_FAILED: Any = object()  # an upstream call errored (already recorded in the report)
_PAREN = re.compile(r"^(.*?)\s*\((.*)\)\s*$")


class _Icd(Protocol):
    async def lookup(self, code: str) -> Icd10Code | None: ...


class _BioPortal(Protocol):
    async def find_concept(self, term: str) -> Concept | None: ...


class _RxNav(Protocol):
    async def rxcui(self, name: str) -> str | None: ...


@dataclass(frozen=True)
class ConditionRef:
    icd10: str
    name: str
    synonyms: list[str]


@dataclass
class CodeRows:
    conditions: list[dict[str, Any]] = field(default_factory=list)
    symptoms: list[dict[str, Any]] = field(default_factory=list)
    drugs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CodeReport:
    icd10_verified: int = 0
    icd10_unknown: list[str] = field(default_factory=list)
    snomed_filled: int = 0
    snomed_missing: int = 0
    snomed_skipped: bool = False  # no BIOPORTAL_API_KEY
    rxcui_filled: int = 0
    rxcui_missing: int = 0
    failed: list[str] = field(default_factory=list)


def concept_terms(name: str, synonyms: list[str]) -> list[str]:
    """'High blood pressure (hypertension)' -> the plain name, the bracketed
    name, the full name, then the synonyms."""
    terms: list[str] = []
    m = _PAREN.match(name)
    if m:
        terms += [m.group(1), m.group(2)]
    terms += [name, *synonyms]
    return list(dict.fromkeys(t for t in terms if t))


async def _first_concept(bp: _BioPortal, terms: list[str]) -> Concept | None:
    for term in terms:
        if concept := await bp.find_concept(term):
            return concept
    return None


async def gather_codes(
    conditions: list[ConditionRef],
    symptoms: list[tuple[str, str]],  # (code, name)
    drugs: list[str],
    icd: _Icd,
    bioportal: _BioPortal | None,
    rxnav: _RxNav,
    *,
    concurrency: int = 8,
) -> tuple[CodeRows, CodeReport]:
    sem = asyncio.Semaphore(concurrency)
    rows, report = CodeRows(), CodeReport(snomed_skipped=bioportal is None)

    async def guarded(label: str, fn: Callable[[], Awaitable[T]]) -> T:
        async with sem:
            try:
                return await fn()
            except MedicalApiError as e:
                report.failed.append(f"{label}: {e}")
                return _FAILED

    def concept_counts(concept: Concept | None) -> dict[str, str | None]:
        if bioportal is None:
            return {"snomed": None, "cui": None}
        if concept:
            report.snomed_filled += 1
        else:
            report.snomed_missing += 1
        return {
            "snomed": concept.snomed if concept else None,
            "cui": concept.cui if concept else None,
        }

    async def condition(ref: ConditionRef) -> dict[str, Any] | None:
        async def work() -> dict[str, Any]:
            code = await icd.lookup(ref.icd10)
            concept = (
                await _first_concept(bioportal, concept_terms(ref.name, ref.synonyms))
                if bioportal
                else None
            )
            return {"code": code, "concept": concept}

        got = await guarded(f"condition {ref.icd10}", work)
        if got is _FAILED:
            return None
        if got["code"]:
            report.icd10_verified += 1
        else:
            report.icd10_unknown.append(ref.icd10)
        return {
            "icd10": ref.icd10,
            "icd10_name": got["code"].name if got["code"] else None,
            **concept_counts(got["concept"]),
        }

    async def symptom(code: str, name: str) -> dict[str, Any] | None:
        async def work() -> Concept | None:
            return await _first_concept(bioportal, concept_terms(name, [])) if bioportal else None

        got = await guarded(f"symptom {code}", work)
        if got is _FAILED:
            return None
        return {"code": code, **concept_counts(got)}

    async def drug(name: str) -> dict[str, Any] | None:
        async def work() -> dict[str, Any]:
            return {"rxcui": await rxnav.rxcui(name)}

        got = await guarded(f"drug {name}", work)
        if got is _FAILED:
            return None
        if got["rxcui"]:
            report.rxcui_filled += 1
        else:
            report.rxcui_missing += 1
        return {"name": name, "rxcui": got["rxcui"]}

    rows.conditions = [r for r in await asyncio.gather(*map(condition, conditions)) if r]
    rows.symptoms = [r for r in await asyncio.gather(*(symptom(c, n) for c, n in symptoms)) if r]
    rows.drugs = [r for r in await asyncio.gather(*map(drug, drugs)) if r]
    return rows, report


async def enrich_codes(
    driver: neo4j.AsyncDriver,
    icd: _Icd,
    bioportal: _BioPortal | None,
    rxnav: _RxNav,
    *,
    concurrency: int = 8,
) -> CodeReport:
    records, _, _ = await driver.execute_query(
        "MATCH (c:Condition) RETURN c.icd10 AS icd10, c.name AS name, c.synonyms AS synonyms"
    )
    conditions = [ConditionRef(r["icd10"], r["name"], r["synonyms"] or []) for r in records]
    records, _, _ = await driver.execute_query("MATCH (s:Symptom) RETURN s.code, s.name")
    symptoms = [(code, name) for code, name in records]
    records, _, _ = await driver.execute_query("MATCH (d:Drug) RETURN d.name ORDER BY d.name")
    drugs = [r[0] for r in records]

    rows, report = await gather_codes(
        conditions, symptoms, drugs, icd, bioportal, rxnav, concurrency=concurrency
    )
    await driver.execute_query(
        "UNWIND $rows AS row MATCH (c:Condition {icd10: row.icd10}) "
        "SET c.icd10_name = row.icd10_name, c.snomed = row.snomed, c.cui = row.cui",
        rows=rows.conditions,
    )
    await driver.execute_query(
        "UNWIND $rows AS row MATCH (s:Symptom {code: row.code}) "
        "SET s.snomed = row.snomed, s.cui = row.cui",
        rows=rows.symptoms,
    )
    await driver.execute_query(
        "UNWIND $rows AS row MATCH (d:Drug {key: row.key}) SET d.rxcui = row.rxcui",
        rows=[{"key": normalise_name(r["name"]), "rxcui": r["rxcui"]} for r in rows.drugs],
    )
    return report
