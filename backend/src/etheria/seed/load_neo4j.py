"""Phases 4-6: drugs, DDInter interactions, the curated domain (spec 6.4).

DDInter nodes and edges are keyed by DDInter id and MERGEd: the files are
checksum-pinned, so a re-run changes nothing. Curated nodes and edges carry a
namespace property `ns`: a curated load deletes its namespace's edges and the
curated nodes the YAML no longer lists, then MERGEs the rest, so the graph
always equals the files. Tests load into their own namespace and never touch
the seeded graph (Neo4j Community has a single database)."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import islice
from typing import Any

import neo4j

from etheria.knowledge.text import normalise_name
from etheria.seed.curated import BODY_SYSTEMS, Curated, ExtraDrug
from etheria.seed.sources import SEVERITY_ORDER

MAIN_NS = "main"
_RANK = {level: i for i, level in enumerate(SEVERITY_ORDER)}


def _batches(rows: Sequence[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    it = iter(rows)
    while chunk := list(islice(it, size)):
        yield chunk


async def _run(driver: neo4j.AsyncDriver, query: str, **params: Any) -> neo4j.ResultSummary:
    _, summary, _ = await driver.execute_query(query, params)
    return summary


async def load_drugs(driver: neo4j.AsyncDriver, drugs: dict[str, str], batch: int = 5000) -> int:
    rows = [{"id": i, "name": n, "key": normalise_name(n)} for i, n in drugs.items()]
    for chunk in _batches(rows, batch):
        await _run(
            driver,
            "UNWIND $rows AS row "
            "MERGE (d:Drug {ddinter_id: row.id}) "
            "SET d.name = row.name, d.key = row.key, d.source = 'ddinter'",
            rows=chunk,
        )
    return len(rows)


async def load_interactions(
    driver: neo4j.AsyncDriver, pairs: dict[tuple[str, str], str], batch: int = 5000
) -> int:
    """Stored lower id -> higher id; queries match either direction."""
    rows = [{"a": a, "b": b, "level": level} for (a, b), level in pairs.items()]
    created = 0
    for chunk in _batches(rows, batch):
        records, _, _ = await driver.execute_query(
            "UNWIND $rows AS row "
            "MATCH (a:Drug {ddinter_id: row.a}) MATCH (b:Drug {ddinter_id: row.b}) "
            "MERGE (a)-[r:INTERACTS_WITH {source: 'ddinter'}]->(b) "
            "SET r.severity = row.level "
            "RETURN count(r)",
            rows=chunk,
        )
        created += records[0][0]
    return created


async def load_extra_drugs(
    driver: neo4j.AsyncDriver, extras: list[ExtraDrug], ns: str = MAIN_NS
) -> int:
    rows = [{"key": normalise_name(d.name), "name": d.name, "atc": d.atc} for d in extras]
    await _run(
        driver,
        "MATCH (d:Drug {source: 'curated', ns: $ns}) WHERE NOT d.key IN $keys DETACH DELETE d",
        ns=ns,
        keys=[r["key"] for r in rows],
    )
    records, _, _ = await driver.execute_query(
        "UNWIND $rows AS row MERGE (d:Drug {key: row.key}) "
        "SET d.name = row.name, d.atc = row.atc, d.source = 'curated', d.ns = $ns "
        "RETURN count(d)",
        rows=rows,
        ns=ns,
    )
    return records[0][0]


@dataclass
class CuratedCounts:
    symptoms: int
    conditions: int
    drug_classes: int
    associated_with: int
    first_line: int
    affects: int
    members_expected: int
    members_created: int
    critical_expected: int
    critical_created: int


def expand_critical(c: Curated) -> dict[tuple[str, str], dict[str, str]]:
    """Class sides -> member drug keys. One edge per unordered pair; if two
    entries cover the same pair, the more severe one wins."""
    members = {k.name: [normalise_name(m) for m in k.members] for k in c.drug_classes}

    def side(s: dict[str, str]) -> list[str]:
        return members[s["class"]] if "class" in s else [normalise_name(s["drug"])]

    out: dict[tuple[str, str], dict[str, str]] = {}
    for ci in c.critical:
        for x in side(ci.a):
            for y in side(ci.b):
                if x == y:
                    continue
                pair = (x, y) if x < y else (y, x)
                old = out.get(pair)
                if old is None or _RANK[ci.severity] < _RANK[old["severity"]]:
                    out[pair] = {
                        "severity": ci.severity,
                        "rationale": ci.rationale,
                        "reference": ci.source,
                    }
    return out


async def load_curated(driver: neo4j.AsyncDriver, c: Curated, ns: str = MAIN_NS) -> CuratedCounts:
    # 1. Forget this namespace's edges and the nodes the files no longer list.
    await _run(driver, "MATCH ()-[r]->() WHERE r.ns = $ns DELETE r", ns=ns)
    await _run(
        driver,
        "MATCH (n) WHERE n.ns = $ns AND ("
        " (n:Condition AND NOT n.icd10 IN $conditions) OR"
        " (n:Symptom AND NOT n.code IN $symptoms) OR"
        " (n:DrugClass AND NOT n.name IN $classes)) DETACH DELETE n",
        ns=ns,
        conditions=[x.icd10 for x in c.conditions],
        symptoms=[s.code for s in c.symptoms],
        classes=[k.name for k in c.drug_classes],
    )

    # 2. Nodes. Body systems are a fixed shared vocabulary, not namespaced.
    await _run(
        driver, "UNWIND $names AS n MERGE (:BodySystem {name: n})", names=sorted(BODY_SYSTEMS)
    )
    await _run(
        driver,
        "UNWIND $rows AS row MERGE (s:Symptom {code: row.code}) "
        "SET s.name = row.name, s.lay_terms = row.lay_terms, s.terms = row.terms, "
        "s.search_text = row.search_text, s.source = row.source, s.ns = $ns",
        rows=[
            {
                "code": s.code,
                "name": s.name,
                "lay_terms": s.lay_terms,
                "terms": sorted({normalise_name(t) for t in [s.name, *s.lay_terms]}),
                "search_text": " | ".join([s.name, *s.lay_terms]),
                "source": s.source,
            }
            for s in c.symptoms
        ],
        ns=ns,
    )
    await _run(
        driver,
        "UNWIND $rows AS row MERGE (c:Condition {icd10: row.icd10}) "
        "SET c.name = row.name, c.synonyms = row.synonyms, c.self_care = row.self_care, "
        "c.red_flags = row.red_flags, c.india_common = row.india_common, "
        "c.source = row.source, c.ns = $ns",
        rows=[
            x.model_dump(
                include={
                    "icd10",
                    "name",
                    "synonyms",
                    "self_care",
                    "red_flags",
                    "india_common",
                    "source",
                }
            )
            for x in c.conditions
        ],
        ns=ns,
    )
    await _run(
        driver,
        "UNWIND $rows AS row MERGE (k:DrugClass {name: row.name}) "
        "SET k.label = row.label, k.ns = $ns",
        rows=[{"name": k.name, "label": k.label} for k in c.drug_classes],
        ns=ns,
    )

    # 3. Edges, all stamped with the namespace.
    async def edges(query: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        records, _, _ = await driver.execute_query(query, rows=rows, ns=ns)
        return records[0][0]

    associated = await edges(
        "UNWIND $rows AS row MATCH (s:Symptom {code: row.s}) MATCH (c:Condition {icd10: row.c}) "
        "CREATE (s)-[r:ASSOCIATED_WITH {weight: row.w, ns: $ns}]->(c) RETURN count(r)",
        [{"s": s, "c": x.icd10, "w": w} for x in c.conditions for s, w in x.symptoms.items()],
    )
    affects = await edges(
        "UNWIND $rows AS row MATCH (c:Condition {icd10: row.c}) MATCH (b:BodySystem {name: row.b}) "
        "CREATE (c)-[r:AFFECTS {ns: $ns}]->(b) RETURN count(r)",
        [{"c": x.icd10, "b": b} for x in c.conditions for b in x.body_systems],
    )
    first_line = await edges(
        "UNWIND $rows AS row MATCH (c:Condition {icd10: row.c}) MATCH (k:DrugClass {name: row.k}) "
        "CREATE (c)-[r:FIRST_LINE {ns: $ns}]->(k) RETURN count(r)",
        [{"c": x.icd10, "k": k} for x in c.conditions for k in x.first_line],
    )
    member_rows = [{"d": normalise_name(m), "k": k.name} for k in c.drug_classes for m in k.members]
    members = await edges(
        "UNWIND $rows AS row MATCH (d:Drug {key: row.d}) MATCH (k:DrugClass {name: row.k}) "
        "CREATE (d)-[r:MEMBER_OF {ns: $ns}]->(k) RETURN count(r)",
        member_rows,
    )
    critical_rows = [{"a": a, "b": b, **props} for (a, b), props in expand_critical(c).items()]
    critical = await edges(
        "UNWIND $rows AS row MATCH (a:Drug {key: row.a}) MATCH (b:Drug {key: row.b}) "
        "CREATE (a)-[r:INTERACTS_WITH {source: 'critical', severity: row.severity, "
        "rationale: row.rationale, reference: row.reference, ns: $ns}]->(b) RETURN count(r)",
        critical_rows,
    )
    return CuratedCounts(
        symptoms=len(c.symptoms),
        conditions=len(c.conditions),
        drug_classes=len(c.drug_classes),
        associated_with=associated,
        first_line=first_line,
        affects=affects,
        members_expected=len(member_rows),
        members_created=members,
        critical_expected=len(critical_rows),
        critical_created=critical,
    )
