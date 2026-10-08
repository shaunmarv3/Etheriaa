"""Phase 8: real counts from the running system and the canaries (spec 6.4).
Every number written to docs/NUMBERS.md comes from a query in this module."""

from dataclasses import dataclass
from pathlib import Path

import neo4j
import psycopg

from etheria.knowledge.conditions import ConditionExplorer
from etheria.knowledge.interactions import InteractionService
from etheria.knowledge.resolver import MedicineResolver
from etheria.knowledge.text import ingredient_candidates, normalise_name

BEGIN = "<!-- seed:begin (written by `uv run etheria seed`; do not edit by hand) -->"
END = "<!-- seed:end -->"


@dataclass(frozen=True)
class Canary:
    name: str
    passed: bool
    detail: str


async def _one(driver: neo4j.AsyncDriver, query: str) -> int:
    records, _, _ = await driver.execute_query(query)
    return records[0][0]


async def graph_counts(driver: neo4j.AsyncDriver) -> dict[str, int]:
    q = {
        "Drug (DDInter)": "MATCH (d:Drug {source: 'ddinter'}) RETURN count(d)",
        "Drug (curated, not in DDInter)": "MATCH (d:Drug {source: 'curated'}) RETURN count(d)",
        "Condition": "MATCH (n:Condition) RETURN count(n)",
        "Symptom": "MATCH (n:Symptom) RETURN count(n)",
        "DrugClass": "MATCH (n:DrugClass) RETURN count(n)",
        "BodySystem": "MATCH (n:BodySystem) RETURN count(n)",
        "INTERACTS_WITH (DDInter)": "MATCH ()-[r:INTERACTS_WITH {source: 'ddinter'}]->() RETURN count(r)",
        "INTERACTS_WITH (DDInter, Major)": "MATCH ()-[r:INTERACTS_WITH {source: 'ddinter', severity: 'Major'}]->() RETURN count(r)",
        "INTERACTS_WITH (critical safety net)": "MATCH ()-[r:INTERACTS_WITH {source: 'critical'}]->() RETURN count(r)",
        "Critical pairs absent from DDInter": "MATCH (a)-[r:INTERACTS_WITH {source: 'critical'}]->(b) "
        "WHERE NOT (a)-[:INTERACTS_WITH {source: 'ddinter'}]-(b) RETURN count(r)",
        "ASSOCIATED_WITH (symptom -> condition)": "MATCH ()-[r:ASSOCIATED_WITH]->() RETURN count(r)",
        "FIRST_LINE (condition -> class)": "MATCH ()-[r:FIRST_LINE]->() RETURN count(r)",
        "MEMBER_OF (drug -> class)": "MATCH ()-[r:MEMBER_OF]->() RETURN count(r)",
        "AFFECTS (condition -> body system)": "MATCH ()-[r:AFFECTS]->() RETURN count(r)",
        "Conditions with a verified ICD-10 name": "MATCH (c:Condition) WHERE c.icd10_name IS NOT NULL RETURN count(c)",
        "Conditions with a SNOMED CT code": "MATCH (c:Condition) WHERE c.snomed IS NOT NULL RETURN count(c)",
        "Symptoms with a SNOMED CT code": "MATCH (s:Symptom) WHERE s.snomed IS NOT NULL RETURN count(s)",
        "Drugs with an RxCUI": "MATCH (d:Drug) WHERE d.rxcui IS NOT NULL RETURN count(d)",
    }
    return {label: await _one(driver, query) for label, query in q.items()}


async def postgres_counts(owner_url: str, driver: neo4j.AsyncDriver) -> dict[str, int]:
    records, _, _ = await driver.execute_query("MATCH (d:Drug) RETURN d.key")
    drug_keys = {r[0] for r in records}
    with psycopg.connect(owner_url) as conn:
        brands, discontinued = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_discontinued) FROM medicine_brands"
        ).fetchone()
        synonyms = dict(
            conn.execute("SELECT lower(alias::text), lower(canonical) FROM drug_synonyms")
        )
        rows = conn.execute(
            "SELECT ingredients, count(*) FROM medicine_brands GROUP BY ingredients"
        ).fetchall()

    def known(ingredient: str) -> bool:
        return any(
            normalise_name(synonyms.get(c, c)) in drug_keys
            for c in ingredient_candidates(ingredient)
        )

    resolvable = sum(n for ingredients, n in rows if ingredients and all(map(known, ingredients)))
    return {
        "medicine_brands": brands,
        "medicine_brands (discontinued)": discontinued,
        "Brands whose every ingredient maps to a graph drug": resolvable,
        "drug_synonyms": len(synonyms),
    }


async def run_canaries(driver: neo4j.AsyncDriver, resolver: MedicineResolver) -> list[Canary]:
    out: list[Canary] = []
    r = await resolver.resolve("Dolo 650")
    out.append(
        Canary(
            "'Dolo 650' resolves to acetaminophen",
            r.ingredients == ["Acetaminophen"],
            f"{r.status}: {r.matched_brand} -> {r.ingredients}",
        )
    )
    service = InteractionService(resolver, driver)
    rep = await service.check(["warfarin", "acetaminophen"])
    ok = any("ddinter" in f.sources for f in rep.findings)
    out.append(
        Canary(
            "warfarin + acetaminophen edge exists (DDInter)",
            ok,
            "; ".join(f"{f.severity} {f.sources}" for f in rep.findings) or "none",
        )
    )
    rep = await service.check(["sertraline", "tramadol"])
    ok = any("critical" in f.sources for f in rep.findings)
    out.append(
        Canary(
            "sertraline + tramadol flagged by the safety net",
            ok,
            "; ".join(f"{f.severity} {f.sources}" for f in rep.findings) or "none",
        )
    )
    matched = await ConditionExplorer(driver).match_symptoms(["loose motions"])
    out.append(
        Canary(
            "'loose motions' matches the diarrhoea symptom",
            matched["loose motions"] == "diarrhoea",
            str(matched["loose motions"]),
        )
    )
    orphans = await _one(
        driver, "MATCH (c:Condition) WHERE NOT (c)<-[:ASSOCIATED_WITH]-() RETURN count(c)"
    )
    out.append(
        Canary("every curated condition has a symptom edge", orphans == 0, f"{orphans} without")
    )
    return out


def render_section(
    counts: dict[str, dict[str, int]], canaries: list[Canary], *, measured_on: str
) -> str:
    lines = [f"## Knowledge layer (measured {measured_on})", ""]
    for group, values in counts.items():
        lines += [f"### {group}", "", "| What | Count |", "|---|---:|"]
        lines += [f"| {k} | {v:,} |" for k, v in values.items()]
        lines.append("")
    lines += ["### Canaries", "", "| Result | Canary | Detail |", "|---|---|---|"]
    lines += [f"| {'PASS' if c.passed else 'FAIL'} | {c.name} | {c.detail} |" for c in canaries]
    return "\n".join(lines)


def write_numbers(path: Path, section: str) -> None:
    block = f"{BEGIN}\n{section}\n{END}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Numbers\n\nEvery number here comes from a query against the running system.\n\n"
            f"{block}\n",
            encoding="utf-8",
        )
        return
    text = path.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        text = head + block + tail
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8")
