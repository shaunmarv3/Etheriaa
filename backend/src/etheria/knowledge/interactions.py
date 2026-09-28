"""Drug-interaction checks (spec 4.5, 6.1). Names are resolved first; every
pair of drugs from *different* products is looked up in both directions.

A pair with no edge is `not_found`, never "safe" (spec 4.6 rule 3), and
names that could not be resolved are listed, never dropped. Pairs inside one
combination product (ibuprofen + paracetamol in Combiflam) are not reported."""

import asyncio
from itertools import combinations

import neo4j
from pydantic import BaseModel

from etheria.cache.json_cache import JsonCache
from etheria.knowledge.resolver import MedicineResolver
from etheria.knowledge.severity import rank
from etheria.knowledge.text import normalise_name

NOT_SAFE_NOTE = (
    "Checked against DDInter 2.0 and a curated list of critical combinations. "
    "'Not found' means no interaction is recorded in these sources, not that the "
    "combination is safe: confirm with a pharmacist or doctor."
)


class InteractionFinding(BaseModel):
    a: str
    b: str
    severity: str  # most severe across sources
    sources: list[str]  # "critical", "ddinter"
    rationale: str | None = None  # from the curated safety net, when present


class InteractionReport(BaseModel):
    findings: list[InteractionFinding]
    not_found: list[tuple[str, str]]
    unresolved: list[str]
    duplicate_ingredients: list[str]  # the same drug in two products (double dosing)
    coverage_note: str = NOT_SAFE_NOTE


GRAPH_TTL_S = 24 * 3600  # knowledge-graph lookups (spec 8.3)


class InteractionService:
    def __init__(
        self,
        resolver: MedicineResolver,
        driver: neo4j.AsyncDriver,
        cache: JsonCache | None = None,
    ) -> None:
        self._resolver = resolver
        self._driver = driver
        self._cache = cache

    async def check(self, names: list[str]) -> InteractionReport:
        resolutions = await asyncio.gather(*(self._resolver.resolve(n) for n in names))
        unresolved: list[str] = []
        products: list[set[str]] = []
        for r in resolutions:
            if r.status == "ambiguous":
                unresolved.append(f"{r.query} (ambiguous)")
            elif r.status == "unresolved":
                unresolved.append(r.query)
            unresolved += [f"{r.query} ({i})" for i in r.unresolved_ingredients]
            # An ambiguous brand still contributes what every candidate contains.
            ingredients = r.ingredients or r.shared_ingredients
            if ingredients:
                products.append(set(ingredients))

        seen: dict[str, int] = {}
        for p in products:
            for d in p:
                seen[d] = seen.get(d, 0) + 1
        duplicates = sorted(d for d, n in seen.items() if n > 1)

        pairs = sorted(
            {
                tuple(sorted((x, y)))
                for p, q in combinations(products, 2)
                for x in p
                for y in q
                if x != y
            }
        )
        edges = await self._edges(pairs)
        findings = []
        for a, b in pairs:
            found = edges.get((a, b))
            if found:
                findings.append(found)
        not_found = [(a, b) for a, b in pairs if (a, b) not in edges]
        findings.sort(key=lambda f: (rank(f.severity), f.a, f.b))
        return InteractionReport(
            findings=findings,
            not_found=not_found,
            unresolved=unresolved,
            duplicate_ingredients=duplicates,
        )

    async def drug_classes(self, drugs: list[str]) -> dict[str, list[str]]:
        """Drug node name -> the DrugClass names it is a member of (for cautions)."""
        records, _, _ = await self._driver.execute_query(
            "UNWIND $rows AS row OPTIONAL MATCH (d:Drug {key: row.k})-[:MEMBER_OF]->(c:DrugClass) "
            "RETURN row.name AS name, collect(DISTINCT c.name) AS classes",
            rows=[{"name": d, "k": normalise_name(d)} for d in drugs],
        )
        return {r["name"]: sorted(r["classes"]) for r in records}

    async def _edges(
        self, pairs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], InteractionFinding]:
        if not pairs:
            return {}
        if self._cache is None:
            records = await self._edge_records(pairs)
        else:
            key = JsonCache.key("kg", "edges", pairs)
            records = await self._cache.get_or_fetch(
                key, GRAPH_TTL_S, lambda: self._edge_records(pairs)
            )
        out = {}
        for a, b, edges in records:
            worst = min(edges, key=lambda e: rank(e["severity"]))
            rationale = next((e["rationale"] for e in edges if e["rationale"]), None)
            out[(a, b)] = InteractionFinding(
                a=a,
                b=b,
                severity=worst["severity"],
                sources=sorted({e["source"] for e in edges}),
                rationale=rationale,
            )
        return out

    async def _edge_records(self, pairs: list[tuple[str, str]]) -> list[list]:
        records, _, _ = await self._driver.execute_query(
            "UNWIND $pairs AS p "
            "MATCH (a:Drug {key: p.ka})-[r:INTERACTS_WITH]-(b:Drug {key: p.kb}) "
            "RETURN p.a AS a, p.b AS b, collect({severity: r.severity, source: r.source, "
            "rationale: r.rationale}) AS edges",
            pairs=[
                {"a": a, "b": b, "ka": normalise_name(a), "kb": normalise_name(b)} for a, b in pairs
            ],
        )
        return [[a, b, list(edges)] for a, b, edges in records]
