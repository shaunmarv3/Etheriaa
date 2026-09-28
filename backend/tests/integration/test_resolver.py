"""The knowledge services against real Postgres (etheria_test, owned by the
tests) and the shared Neo4j (uniquely tagged nodes, deleted afterwards)."""

import uuid
from collections.abc import AsyncIterator

import neo4j
import psycopg
import pytest

from etheria.core.settings import Settings
from etheria.db.session import Database
from etheria.knowledge.conditions import ConditionExplorer
from etheria.knowledge.interactions import NOT_SAFE_NOTE, InteractionService
from etheria.knowledge.neo4j import create_driver
from etheria.knowledge.resolver import MedicineResolver
from etheria.knowledge.schema import apply_schema
from etheria.seed.curated import Condition, Curated, Symptom
from etheria.seed.load_neo4j import load_curated, load_drugs

SRC = "https://medlineplus.gov/x.html"


@pytest.fixture
def tag() -> str:
    return "zztest" + uuid.uuid4().hex[:8]


@pytest.fixture
async def driver(settings: Settings, tag: str) -> AsyncIterator[neo4j.AsyncDriver]:
    d = create_driver(settings)
    await apply_schema(d)
    yield d
    await d.execute_query(
        "MATCH (n) WHERE n.ns = $t OR n.ddinter_id STARTS WITH $t OR n.key STARTS WITH $t "
        "DETACH DELETE n",
        t=tag,
    )
    await d.close()


@pytest.fixture
async def world(owner_conn: psycopg.Connection, driver: neo4j.AsyncDriver, tag: str) -> str:
    """Brands and synonyms in Postgres; drugs and edges in Neo4j."""
    p, ibu, w = f"{tag}paracetamol", f"{tag}ibuprofen", f"{tag}warfarin"
    owner_conn.execute("TRUNCATE medicine_brands RESTART IDENTITY")
    with owner_conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO medicine_brands (name, ingredients) VALUES (%s, %s)",
            [
                ("Dolo 650 Tablet", [p]),
                ("Dolo 500 Tablet", [p]),
                ("Calpol 650 Tablet", [p]),
                ("Combiflam Tablet", [ibu, p]),
                ("Warf 5 Tablet", [w]),
                ("Tramazac 50 Capsule", [f"{tag}tramadol"]),
                ("Tramazax 50 Capsule", [f"{tag}sertraline"]),
                ("Oddmed Tablet", [f"{tag}notinddinter"]),
            ],
        )
    owner_conn.execute(
        "INSERT INTO drug_synonyms VALUES (%s, %s) ON CONFLICT (alias) DO UPDATE "
        "SET canonical = excluded.canonical",
        (p, f"{tag}Acetaminophen"),
    )
    await load_drugs(
        driver,
        {
            f"{tag}{i}": f"{tag}{n}"
            for i, n in enumerate(
                ["Acetaminophen", "Ibuprofen", "Warfarin", "Tramadol", "Sertraline"]
            )
        },
    )
    edges = [
        ("acetaminophen", "warfarin", "Moderate", "ddinter"),
        ("ibuprofen", "warfarin", "Major", "ddinter"),
        ("ibuprofen", "warfarin", "Major", "critical"),
        ("sertraline", "tramadol", "Major", "critical"),
    ]
    for a, b, sev, src in edges:
        await driver.execute_query(
            "MATCH (a:Drug {key: $a}), (b:Drug {key: $b}) "
            "CREATE (a)-[:INTERACTS_WITH {severity: $sev, source: $src, rationale: 'r'}]->(b)",
            a=tag + a,
            b=tag + b,
            sev=sev,
            src=src,
        )
    return tag


@pytest.fixture
def resolver(db: Database, driver: neo4j.AsyncDriver) -> MedicineResolver:
    return MedicineResolver(db, driver)


@pytest.mark.parametrize("query", ["Dolo 650", "DOLO 650", "dolo-650", "Dolo 650 tab"])
async def test_resolver_brand_noise_resolves(
    resolver: MedicineResolver, world: str, query: str
) -> None:
    r = await resolver.resolve(query)
    assert r.status == "resolved"
    assert r.ingredients == [f"{world}Acetaminophen"]
    assert r.matched_brand and r.matched_brand.startswith("Dolo")


async def test_resolver_ingredient_and_synonym_directly(
    resolver: MedicineResolver, world: str
) -> None:
    r = await resolver.resolve(f"{world}paracetamol")
    assert (r.status, r.matched_brand, r.ingredients) == (
        "resolved",
        None,
        [f"{world}Acetaminophen"],
    )
    r = await resolver.resolve(f"{world}warfarin")
    assert r.ingredients == [f"{world}Warfarin"]


async def test_resolver_combination_brand(resolver: MedicineResolver, world: str) -> None:
    r = await resolver.resolve("Combiflam")
    assert sorted(r.ingredients) == sorted([f"{world}Ibuprofen", f"{world}Acetaminophen"])


async def test_resolver_ambiguous_is_not_guessed(resolver: MedicineResolver, world: str) -> None:
    r = await resolver.resolve("Tramaza 50")
    assert r.status == "ambiguous"
    assert r.ingredients == []
    assert set(r.candidates) == {"Tramazac 50 Capsule", "Tramazax 50 Capsule"}


async def test_resolver_unknown_and_unmapped(resolver: MedicineResolver, world: str) -> None:
    r = await resolver.resolve("qwertyuiop")
    assert (r.status, r.ingredients) == ("unresolved", [])
    r = await resolver.resolve("Oddmed Tablet")
    assert r.status == "resolved"
    assert r.ingredients == []
    assert r.unresolved_ingredients == [f"{world}notinddinter"]
    r = await resolver.resolve("   ")
    assert r.status == "unresolved"


async def test_interaction_found_via_brands(
    resolver: MedicineResolver, driver: neo4j.AsyncDriver, world: str
) -> None:
    report = await InteractionService(resolver, driver).check(["Warf 5", "Dolo 650"])
    assert [(f.severity, f.sources) for f in report.findings] == [("Moderate", ["ddinter"])]
    assert report.not_found == [] and report.unresolved == []


async def test_most_severe_across_sources_and_no_pairs_inside_one_product(
    resolver: MedicineResolver, driver: neo4j.AsyncDriver, world: str
) -> None:
    report = await InteractionService(resolver, driver).check(["Combiflam", "Warf 5"])
    got = {(f.a, f.b): (f.severity, f.sources) for f in report.findings}
    ibu = next(k for k in got if f"{world}Ibuprofen" in k)
    assert got[ibu] == ("Major", ["critical", "ddinter"])
    assert len(report.findings) == 2  # ibuprofen+warfarin, acetaminophen+warfarin
    assert all(
        {f.a, f.b} != {f"{world}Ibuprofen", f"{world}Acetaminophen"} for f in report.findings
    )


async def test_missing_edge_is_not_found_never_safe(
    resolver: MedicineResolver, driver: neo4j.AsyncDriver, world: str
) -> None:
    report = await InteractionService(resolver, driver).check(
        [f"{world}sertraline", f"{world}ibuprofen"]
    )
    assert report.findings == []
    assert report.not_found == [(f"{world}Ibuprofen", f"{world}Sertraline")]
    assert report.coverage_note == NOT_SAFE_NOTE
    assert "not that the combination is safe" in NOT_SAFE_NOTE


async def test_safety_net_edge_and_unresolved_names(
    resolver: MedicineResolver, driver: neo4j.AsyncDriver, world: str
) -> None:
    report = await InteractionService(resolver, driver).check(
        [f"{world}sertraline", f"{world}tramadol", "Tramaza 50", "qwertyuiop"]
    )
    assert [(f.severity, f.sources) for f in report.findings] == [("Major", ["critical"])]
    assert report.unresolved == ["Tramaza 50 (ambiguous)", "qwertyuiop"]


async def test_duplicate_ingredient_across_products(
    resolver: MedicineResolver, driver: neo4j.AsyncDriver, world: str
) -> None:
    report = await InteractionService(resolver, driver).check(["Dolo 650", "Calpol 650"])
    assert report.duplicate_ingredients == [f"{world}Acetaminophen"]


async def test_condition_explorer(driver: neo4j.AsyncDriver, tag: str) -> None:
    curated = Curated(
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
        conditions=[
            Condition(
                icd10="Z99.B1",
                name=f"{tag} dengue",
                body_systems=["Infectious"],
                india_common=True,
                symptoms={f"{tag}_fever": 1.0, f"{tag}_loose": 0.4},
                self_care=["Rest"],
                red_flags=["Bleeding"],
                source=SRC,
            ),
            Condition(
                icd10="Z99.B2",
                name=f"{tag} gastro",
                body_systems=["Gastrointestinal"],
                india_common=True,
                symptoms={f"{tag}_loose": 1.0},
                source=SRC,
            ),
        ],
        drug_classes=[],
        critical=[],
        synonyms={},
    )
    await load_curated(driver, curated, ns=tag)
    explorer = ConditionExplorer(driver)
    matched = await explorer.match_symptoms(
        [f"{tag.upper()} Loose Motions", f"{tag} motions", "xyzzy nothing"]
    )
    assert matched == {
        f"{tag.upper()} Loose Motions": f"{tag}_loose",  # exact lay term, any case
        f"{tag} motions": f"{tag}_loose",  # full-text fallback: every word must match
        "xyzzy nothing": None,
    }
    result = await explorer.explore([f"{tag} bukhar", f"{tag} loose motions"], k=5)
    assert [h.icd10 for h in result.conditions] == ["Z99.B1", "Z99.B2"]
    top = result.conditions[0]
    assert top.score == pytest.approx(1.4)
    assert sorted(top.matched_symptoms) == [f"{tag} diarrhoea", f"{tag} fever"]
    assert top.red_flags == ["Bleeding"]
    assert result.unmatched == []
