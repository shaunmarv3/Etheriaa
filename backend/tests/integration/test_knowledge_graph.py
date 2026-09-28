"""Neo4j schema and loaders against the real Neo4j. Community edition has one
database, shared with the seeded graph, so every test works in its own
namespace (`ns`) and on uniquely named drugs, and deletes them afterwards."""

import uuid
from collections.abc import AsyncIterator

import neo4j
import pytest

from etheria.core.settings import Settings
from etheria.knowledge.neo4j import create_driver
from etheria.knowledge.schema import apply_schema
from etheria.seed.curated import (
    Condition,
    CriticalInteraction,
    Curated,
    DrugClass,
    ExtraDrug,
    Symptom,
)
from etheria.seed.load_neo4j import load_curated, load_drugs, load_extra_drugs, load_interactions

SRC = "https://medlineplus.gov/x.html"


@pytest.fixture
async def driver(settings: Settings) -> AsyncIterator[neo4j.AsyncDriver]:
    d = create_driver(settings)
    await apply_schema(d)
    yield d
    await d.close()


@pytest.fixture
def tag() -> str:
    return "zztest" + uuid.uuid4().hex[:8]


@pytest.fixture
async def cleanup(driver: neo4j.AsyncDriver, tag: str) -> AsyncIterator[None]:
    yield
    await driver.execute_query(
        "MATCH (n) WHERE n.ns = $tag OR n.ddinter_id STARTS WITH $tag OR n.key STARTS WITH $tag "
        "DETACH DELETE n",
        tag=tag,
    )


async def count(driver: neo4j.AsyncDriver, query: str, **params) -> int:
    records, _, _ = await driver.execute_query(query, params)
    return records[0][0]


def drugs(tag: str) -> dict[str, str]:
    return {
        f"{tag}1": f"{tag} Warfarin",
        f"{tag}2": f"{tag} Acetaminophen",
        f"{tag}3": f"{tag} Sertraline",
        f"{tag}4": f"{tag} Tramadol",
    }


def curated(tag: str, *, with_second_condition: bool = True) -> Curated:
    conditions = [
        Condition(
            icd10="Z99.A1",
            name=f"{tag} dengue",
            body_systems=["Infectious"],
            india_common=True,
            symptoms={f"{tag}_fever": 1.0, f"{tag}_loose": 0.4},
            first_line=[f"{tag}_antipyretic"],
            self_care=["Rest"],
            red_flags=["Bleeding"],
            source=SRC,
        ),
    ]
    if with_second_condition:
        conditions.append(
            Condition(
                icd10="Z99.A2",
                name=f"{tag} gastro",
                body_systems=["Gastrointestinal"],
                india_common=True,
                symptoms={f"{tag}_loose": 1.0},
                source=SRC,
            )
        )
    return Curated(
        symptoms=[
            Symptom(
                code=f"{tag}_fever", name=f"{tag} fever", lay_terms=[f"{tag} bukhar"], source=SRC
            ),
            Symptom(
                code=f"{tag}_loose",
                name=f"{tag} diarrhoea",
                lay_terms=[f"{tag} loose motions"],
                source=SRC,
            ),
        ],
        conditions=conditions,
        drug_classes=[
            DrugClass(
                name=f"{tag}_antipyretic", label="Antipyretic", members=[f"{tag} Acetaminophen"]
            ),
            DrugClass(
                name=f"{tag}_ssri", label="SSRI", members=[f"{tag} Sertraline", f"{tag} Escitalo"]
            ),
        ],
        critical=[
            CriticalInteraction(
                a={"class": f"{tag}_ssri"},
                b={"drug": f"{tag} Tramadol"},
                severity="Major",
                rationale="Serotonin syndrome.",
                source=SRC,
            )
        ],
        synonyms={},
        extra_drugs=[ExtraDrug(name=f"{tag} Escitalo", atc="N06AB10", source=SRC)],
    )


async def test_schema_is_idempotent(driver: neo4j.AsyncDriver) -> None:
    await apply_schema(driver)
    records, _, _ = await driver.execute_query("SHOW CONSTRAINTS YIELD name RETURN collect(name)")
    names = set(records[0][0])
    assert {"drug_ddinter_id", "drug_key", "condition_icd10", "symptom_code"} <= names
    records, _, _ = await driver.execute_query(
        "SHOW FULLTEXT INDEXES YIELD name RETURN collect(name)"
    )
    assert {"drug_name", "symptom_text"} <= set(records[0][0])


async def test_drugs_and_pairs_reload_without_duplicates(
    driver: neo4j.AsyncDriver, tag: str, cleanup: None
) -> None:
    pairs = {(f"{tag}1", f"{tag}2"): "Moderate"}
    for _ in range(2):
        assert await load_drugs(driver, drugs(tag), batch=2) == 4
        assert await load_interactions(driver, pairs, batch=2) == 1
    assert (
        await count(
            driver, "MATCH (d:Drug) WHERE d.ddinter_id STARTS WITH $t RETURN count(d)", t=tag
        )
        == 4
    )
    assert (
        await count(
            driver,
            "MATCH (:Drug {ddinter_id: $a})-[r:INTERACTS_WITH]-(:Drug {ddinter_id: $b}) "
            "RETURN count(r)",
            a=f"{tag}1",
            b=f"{tag}2",
        )
        == 1
    )
    rec, _, _ = await driver.execute_query(
        "MATCH (d:Drug {ddinter_id: $id}) RETURN d.key, d.name, d.source", id=f"{tag}1"
    )
    assert tuple(rec[0]) == (f"{tag} warfarin", f"{tag} Warfarin", "ddinter")


async def test_interaction_found_in_both_directions(
    driver: neo4j.AsyncDriver, tag: str, cleanup: None
) -> None:
    await load_drugs(driver, drugs(tag))
    await load_interactions(driver, {(f"{tag}1", f"{tag}2"): "Moderate"})
    q = "MATCH (:Drug {key: $x})-[r:INTERACTS_WITH]-(:Drug {key: $y}) RETURN r.severity, r.source"
    for x, y in [("warfarin", "acetaminophen"), ("acetaminophen", "warfarin")]:
        rec, _, _ = await driver.execute_query(q, x=f"{tag} {x}", y=f"{tag} {y}")
        assert [tuple(r) for r in rec] == [("Moderate", "ddinter")]


async def test_curated_graph_with_class_expanded_safety_net(
    driver: neo4j.AsyncDriver, tag: str, cleanup: None
) -> None:
    await load_drugs(driver, drugs(tag))
    assert await load_extra_drugs(driver, curated(tag).extra_drugs, ns=tag) == 1
    counts = await load_curated(driver, curated(tag), ns=tag)
    assert (
        counts.critical_expected == counts.critical_created == 2
    )  # sertraline, escitalo x tramadol
    assert counts.members_expected == counts.members_created == 3
    rec, _, _ = await driver.execute_query(
        "MATCH (:Drug {key: $s})-[r:INTERACTS_WITH {source: 'critical'}]-(:Drug {key: $t}) "
        "RETURN r.severity, r.rationale, r.reference",
        s=f"{tag} escitalo",
        t=f"{tag} tramadol",
    )
    assert [tuple(r) for r in rec] == [("Major", "Serotonin syndrome.", SRC)]
    assert (
        await count(
            driver,
            "MATCH (s:Symptom {code: $c})-[r:ASSOCIATED_WITH]->(c:Condition) RETURN count(c)",
            c=f"{tag}_loose",
        )
        == 2
    )
    rec, _, _ = await driver.execute_query(
        "MATCH (s:Symptom {code: $c}) RETURN s.terms, s.search_text", c=f"{tag}_loose"
    )
    terms, text = rec[0]
    assert f"{tag} loose motions" in terms and f"{tag} diarrhoea" in terms
    assert "loose motions" in text
    assert (
        await count(
            driver,
            "MATCH (:Condition {icd10: 'Z99.A1'})-[:FIRST_LINE]->(k:DrugClass)"
            "<-[:MEMBER_OF]-(d:Drug) RETURN count(d)",
        )
        == 1
    )
    assert (
        await count(
            driver,
            "MATCH (:Condition {icd10: 'Z99.A1'})-[:AFFECTS]->(b:BodySystem) RETURN count(b)",
        )
        == 1
    )


async def test_curated_reload_prunes_what_the_yaml_no_longer_has(
    driver: neo4j.AsyncDriver, tag: str, cleanup: None
) -> None:
    await load_drugs(driver, drugs(tag))
    await load_extra_drugs(driver, curated(tag).extra_drugs, ns=tag)
    await load_curated(driver, curated(tag), ns=tag)
    first = await count(driver, "MATCH ()-[r]->() WHERE r.ns = $t RETURN count(r)", t=tag)
    await load_curated(driver, curated(tag), ns=tag)  # re-run: same graph
    before = await count(driver, "MATCH ()-[r]->() WHERE r.ns = $t RETURN count(r)", t=tag)
    assert before == first
    await load_curated(driver, curated(tag, with_second_condition=False), ns=tag)
    assert await count(driver, "MATCH (c:Condition {icd10: 'Z99.A2'}) RETURN count(c)") == 0
    after = await count(driver, "MATCH ()-[r]->() WHERE r.ns = $t RETURN count(r)", t=tag)
    assert after == before - 2  # the gastro condition's ASSOCIATED_WITH + AFFECTS


async def test_other_namespaces_are_untouched(
    driver: neo4j.AsyncDriver, tag: str, cleanup: None
) -> None:
    other = tag + "b"
    try:
        await load_drugs(driver, drugs(tag))
        await load_curated(driver, curated(tag, with_second_condition=False), ns=tag)
        before = await count(driver, "MATCH ()-[r]->() WHERE r.ns = $t RETURN count(r)", t=tag)
        await load_curated(
            driver,
            Curated(symptoms=[], conditions=[], drug_classes=[], critical=[], synonyms={}),
            ns=other,
        )
        assert (
            await count(driver, "MATCH ()-[r]->() WHERE r.ns = $t RETURN count(r)", t=tag) == before
        )
    finally:
        await driver.execute_query("MATCH (n {ns: $o}) DETACH DELETE n", o=other)
