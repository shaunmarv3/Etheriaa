"""The retrieval agent's tools (spec 4.5).

LangGraph/LangChain concepts: `@tool(response_format="content_and_artifact")`
returns two things: compact JSON the model reads, and a list of `Evidence`
objects (the artifact) that code collects for citations. `runtime: ToolRuntime`
is injected by the agent and hidden from the model's schema: `runtime.context`
is the trusted `ChatContext` (the user id comes only from there, never from an
argument) and `runtime.state` is the agent's own state (the test catalogue and a
stated pregnancy, plan Decision 7).

Every tool is async, read-only, bounded by a per-tool timeout, and never raises
into the agent: a failure comes back as {"error": ...}."""

import asyncio
import json
from collections.abc import Awaitable
from typing import Any

from langchain.tools import ToolRuntime, tool

from etheria.db.repositories import health_record as hr
from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import lab_line, log
from etheria.graph.schemas import Evidence
from etheria.knowledge.resolver import Resolution
from etheria.retrieval.hybrid import search_reports as hybrid_search
from etheria.safety.cautions import DrugClasses, LabObservation, evaluate
from etheria.safety.texts import NO_CAUTION_WORDING, NOT_FOUND_WORDING

Result = tuple[str, list[Evidence]]
MAX_REPORT_K = 8
MAX_PUBMED_K = 5
DOC_TYPES = {"lab_report", "prescription", "discharge_summary", "imaging_report", "other"}


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)


async def _bounded(name: str, work: Awaitable[Result], timeout_s: float) -> Result:
    try:
        return await asyncio.wait_for(work, timeout_s)
    except TimeoutError:
        log.warning("tool_timeout", tool=name)
        return _json({"error": "timeout"}), []
    except Exception as e:
        log.warning("tool_failed", tool=name, error=type(e).__name__)
        return _json({"error": "unavailable"}), []


def _lab_evidence(f: hr.LabFact, tool_name: str) -> Evidence:
    return Evidence(
        id=f"lab:{f.id}",
        source="user_document",
        kind="lab",
        identifier=f.document_id,
        title=f"Your report {f.filename}" + (f", {f.report_date}" if f.report_date else ""),
        text=lab_line(f),
        structured=True,
        tool=tool_name,
    )


def _variant_list(r: Resolution) -> str:
    parts = [f"{', '.join(v.brands)} ({' + '.join(v.ingredients)})" for v in r.variants]
    if r.more_variants:
        parts.append(f"and {r.more_variants} more combinations")
    return "; ".join(parts)


def _medicine_evidence(name: str, r: Resolution, tool_name: str) -> Evidence:
    if r.status == "resolved":
        text = f"{name} contains {', '.join(r.ingredients) or 'unrecognised ingredients'}"
        if r.matched_brand:
            text += f" (brand {r.matched_brand})"
        if r.variants:
            text += (
                f". Other products sold under a similar name contain different ingredients, "
                f"so the user should check which one is on the strip: {_variant_list(r)}. "
                f"Only the ingredients of {r.matched_brand} were checked"
            )
    elif r.status == "ambiguous":
        shared = ", ".join(r.shared_ingredients)
        text = f"{name} could be any of several products: {_variant_list(r)}; " + (
            f"all of them contain {shared}, which was checked; any other ingredient was not "
            "checked, so the user should confirm which product they have"
            if shared
            else "they share no ingredient, so it could not be checked"
        )
    else:
        text = f"{name} could not be identified"
    return Evidence(
        id=f"medicine:{name.lower()}",
        source="neo4j",
        kind="note",
        identifier=name,
        title=f"Medicine lookup: {name}",
        text=text,
        structured=True,
        tool=tool_name,
    )


def make_tools(deps: GraphDeps) -> list:
    t = deps.tool_timeout_s

    @tool(response_format="content_and_artifact")
    async def get_lab_values(
        test_names: list[str], runtime: ToolRuntime, include_abnormal: bool = False
    ) -> Result:
        """The user's own lab results for the named tests, from all their reports,
        newest first. test_names must come from the user's test catalogue. Set
        include_abnormal=true to also get every abnormal value on their reports."""

        async def work() -> Result:
            catalogue = {n.lower(): n for n in runtime.state.get("test_catalogue", [])}
            known = [catalogue[n.lower()] for n in test_names if n.lower() in catalogue]
            unknown = [n for n in test_names if n.lower() not in catalogue]
            user_id = runtime.context.user_id
            async with deps.db.for_user(user_id) as s:
                facts = await hr.lab_values(s, user_id, known, include_abnormal)
            evidence = [_lab_evidence(f, "get_lab_values") for f in facts]
            content = {
                "results": [{"evidence_id": e.id, "value": e.text} for e in evidence],
                "not_in_catalogue": unknown,
            }
            return _json(content), evidence

        return await _bounded("get_lab_values", work(), t)

    @tool(response_format="content_and_artifact")
    async def get_current_medications(runtime: ToolRuntime) -> Result:
        """The medicines on the user's uploaded prescriptions and discharge
        summaries, with the ingredients each brand contains."""

        async def work() -> Result:
            user_id = runtime.context.user_id
            async with deps.db.for_user(user_id) as s:
                meds = await hr.medications(s, user_id)
            resolutions = await asyncio.gather(*(deps.resolver.resolve(m.name_raw) for m in meds))
            evidence = []
            for m, r in zip(meds, resolutions, strict=True):
                ingredients = r.ingredients or r.shared_ingredients
                contains = f" (contains {', '.join(ingredients)})" if ingredients else ""
                source = m.source.replace("_", " ")
                evidence.append(
                    Evidence(
                        id=f"med:{m.id}",
                        source="user_document",
                        kind="medication",
                        identifier=m.document_id or m.id,
                        title=f"Your {source}" + (f", {m.report_date}" if m.report_date else ""),
                        text=f"{m.name_raw}{contains}, listed on the user's {source}",
                        structured=True,
                        tool="get_current_medications",
                    )
                )
            return _json([{"evidence_id": e.id, "medicine": e.text} for e in evidence]), evidence

        return await _bounded("get_current_medications", work(), t)

    @tool(response_format="content_and_artifact")
    async def search_my_reports(
        query: str, runtime: ToolRuntime, doc_types: list[str] | None = None, k: int = 6
    ) -> Result:
        """Search the text of the user's own uploaded documents (discharge
        summaries, prescriptions, imaging reports, lab reports). Use a short
        English query. doc_types can limit the search, e.g. ["discharge_summary"]."""

        async def work() -> Result:
            user_id = runtime.context.user_id
            types = [d for d in doc_types or [] if d in DOC_TYPES] or None
            vec = await deps.query_embedder.embed_query(query)
            async with deps.db.for_user(user_id) as s:
                hits = await hybrid_search(
                    s, user_id, vec, query, k=max(1, min(k, MAX_REPORT_K)), doc_types=types
                )
            evidence = [
                Evidence(
                    id=f"chunk:{h.id}",
                    source="user_document",
                    kind="chunk",
                    identifier=h.document_id,
                    title=f"Your report {h.filename}" + (f", page {h.page}" if h.page else ""),
                    text=h.content,
                    relevance=h.score,
                    tool="search_my_reports",
                )
                for h in hits
            ]
            content = [{"evidence_id": e.id, "from": e.title} for e in evidence]
            return _json({"passages_found": content}), evidence

        return await _bounded("search_my_reports", work(), t)

    @tool(response_format="content_and_artifact")
    async def search_medical_literature(query: str, k: int = 3) -> Result:
        """Search PubMed abstracts. Use for what research says or for a specific
        medical fact that needs a study. Use a short English query."""

        async def work() -> Result:
            articles = await deps.pubmed.search_articles(query, max(1, min(k, MAX_PUBMED_K)))
            evidence = [
                Evidence(
                    id=f"pubmed:{a.pmid}",
                    source="pubmed",
                    kind="pubmed",
                    identifier=a.pmid,
                    title=a.title + (f" ({a.year})" if a.year else ""),
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{a.pmid}/",
                    text=a.abstract[:1200],
                    relevance=0.5,
                    tool="search_medical_literature",
                )
                for a in articles
            ]
            return _json([{"evidence_id": e.id, "title": e.title} for e in evidence]), evidence

        return await _bounded("search_medical_literature", work(), t)

    @tool(response_format="content_and_artifact")
    async def search_health_topics(query: str) -> Result:
        """Plain-language health summaries from MedlinePlus (US National Library
        of Medicine) about a condition, symptom, test or medicine. Use a short
        English query."""

        async def work() -> Result:
            topics = await deps.medlineplus.search(query, 3)
            evidence = [
                Evidence(
                    id=f"medlineplus:{tp.url}",
                    source="medlineplus",
                    kind="medlineplus",
                    identifier=tp.url,
                    title=f"MedlinePlus: {tp.title}",
                    url=tp.url,
                    text=tp.summary[:1500],
                    relevance=0.5,
                    tool="search_health_topics",
                )
                for tp in topics
            ]
            return _json([{"evidence_id": e.id, "title": e.title} for e in evidence]), evidence

        return await _bounded("search_health_topics", work(), t)

    @tool(response_format="content_and_artifact")
    async def explore_conditions(symptoms: list[str]) -> Result:
        """India-common conditions associated with the given symptoms, from a
        curated medical graph, with first-line treatment classes (never doses),
        self-care and red flags. Pass clean symptom phrases like "headache",
        "loose motions", not whole sentences."""

        async def work() -> Result:
            result = await deps.explorer.explore(symptoms, k=5)
            evidence = [
                Evidence(
                    id=f"condition:{c.icd10}",
                    source="neo4j",
                    kind="condition",
                    identifier=c.icd10,
                    title=f"Curated condition: {c.name}",
                    text=(
                        f"{c.name} (ICD-10 {c.icd10}); matches {', '.join(c.matched_symptoms)}; "
                        "first-line treatment classes: "
                        f"{', '.join(c.first_line_classes) or 'none'}; "
                        f"self-care: {'; '.join(c.self_care) or 'none'}; "
                        f"red flags: {'; '.join(c.red_flags) or 'none'}"
                    ),
                    relevance=round(c.coverage, 3),
                    structured=True,
                    tool="explore_conditions",
                )
                for c in result.conditions
            ]
            content = {
                "matched_symptoms": result.matched,
                "unmatched": result.unmatched,
                "conditions": [
                    {"evidence_id": e.id, "name": c.name, "coverage": round(c.coverage, 2)}
                    for e, c in zip(evidence, result.conditions, strict=True)
                ],
            }
            return _json(content), evidence

        return await _bounded("explore_conditions", work(), t)

    @tool(response_format="content_and_artifact")
    async def resolve_medicine(name: str) -> Result:
        """What an Indian brand or generic medicine name contains (its
        ingredients). Close brand variants with different ingredients are
        reported as ambiguous with the candidates."""

        async def work() -> Result:
            e = _medicine_evidence(name, await deps.resolver.resolve(name), "resolve_medicine")
            return _json({"evidence_id": e.id, "result": e.text}), [e]

        return await _bounded("resolve_medicine", work(), t)

    @tool(response_format="content_and_artifact")
    async def check_interactions(
        drugs: list[str], runtime: ToolRuntime, include_current_medications: bool = True
    ) -> Result:
        """Check medicines (brand or generic names) against each other, against
        the user's current medicines, and against the user's own lab values,
        diagnoses and a stated pregnancy. A pair with no recorded interaction is
        'not found', which is never the same as safe."""

        async def work() -> Result:
            user_id = runtime.context.user_id
            async with deps.db.for_user(user_id) as s:
                current = await hr.medications(s, user_id) if include_current_medications else []
                labs = await hr.lab_snapshot(s, user_id)
                conditions = await hr.conditions(s, user_id)
            names = list(dict.fromkeys([*drugs, *(m.name_raw for m in current)]))
            report = await deps.interactions.check(names)
            resolutions = await asyncio.gather(*(deps.resolver.resolve(d) for d in drugs))
            # Say what each asked-about name is; an ambiguous brand still has the
            # ingredient all its variants share, and that ingredient was checked.
            evidence: list[Evidence] = [
                _medicine_evidence(d, r, "check_interactions")
                for d, r in zip(drugs, resolutions, strict=True)
                if r.status != "resolved" or r.matched_brand
            ]
            for f in report.findings:
                evidence.append(
                    Evidence(
                        id=f"interaction:{f.a}|{f.b}",
                        source="neo4j",
                        kind="interaction",
                        identifier=f"{f.a} + {f.b}",
                        title=f"Interaction check: {f.a} + {f.b}",
                        text=(
                            f"{f.a} + {f.b}: {f.severity} interaction recorded "
                            f"(sources: {', '.join(f.sources)})"
                            + (f". {f.rationale}" if f.rationale else "")
                        ),
                        structured=True,
                        tool="check_interactions",
                    )
                )
            if report.not_found:
                pairs = "; ".join(f"{a} + {b}" for a, b in report.not_found)
                evidence.append(
                    Evidence(
                        id="interaction:not_found",
                        source="neo4j",
                        kind="interaction",
                        identifier="not found",
                        title="Interaction check: not found",
                        text=(
                            f"Not found in DDInter or the curated list: {pairs}. "
                            + NOT_FOUND_WORDING
                        ),
                        structured=True,
                        tool="check_interactions",
                    )
                )
            if report.duplicate_ingredients:
                evidence.append(
                    Evidence(
                        id="interaction:duplicates",
                        source="neo4j",
                        kind="interaction",
                        identifier="same ingredient",
                        title="Interaction check: same ingredient twice",
                        text=(
                            "The same ingredient is in more than one of these products (risk of "
                            f"taking a double amount): {', '.join(report.duplicate_ingredients)}"
                        ),
                        structured=True,
                        tool="check_interactions",
                    )
                )
            if report.unresolved:
                evidence.append(
                    Evidence(
                        id="interaction:unresolved",
                        source="neo4j",
                        kind="note",
                        identifier="unresolved",
                        title="Interaction check: names not identified",
                        text=(
                            "Could not identify with certainty (so not fully checked): "
                            + ", ".join(report.unresolved)
                        ),
                        structured=True,
                        tool="check_interactions",
                    )
                )
            evidence += await _cautions(resolutions, labs, conditions, runtime)
            content = {
                "evidence": [{"evidence_id": e.id, "fact": e.text} for e in evidence],
                "coverage_note": report.coverage_note,
            }
            return _json(content), evidence

        return await _bounded("check_interactions", work(), t)

    async def _cautions(
        resolutions: list[Resolution],
        labs: list[hr.LabFact],
        conditions: list[str],
        runtime: ToolRuntime,
    ) -> list[Evidence]:
        ingredients = sorted(
            {i for r in resolutions for i in (r.ingredients or r.shared_ingredients)}
        )
        if not ingredients:
            return []
        classes = await deps.interactions.drug_classes(ingredients)
        found = evaluate(
            [DrugClasses(drug=d, classes=classes.get(d, [])) for d in ingredients],
            [
                LabObservation(
                    id=f.id,
                    test_name=f.test_name,
                    value_text=f.value_text,
                    unit=f.unit,
                    flag=f.flag,
                    report_date=f.report_date,
                )
                for f in labs
            ],
            conditions,
            bool(runtime.state.get("pregnant", False)),
            deps.cautions,
        )
        by_id = {f.id: f for f in labs}
        out = []
        for c in found:
            lab = by_id.get(c.lab_id or "")
            where = (
                f" on {lab.filename}" + (f" ({lab.report_date})" if lab.report_date else "")
                if lab
                else ""
            )
            value = f" {c.value}" if c.value else ""
            out.append(
                Evidence(
                    id=f"caution:{c.rule_id}:{c.lab_id or c.trigger}",
                    source="curated",
                    kind="caution",
                    identifier=c.rule_id,
                    title=f"Caution from your record: {c.drug}",
                    url=c.source,
                    text=f"{c.drug} with {c.trigger}{value}{where}: {c.rationale}",
                    structured=True,
                    tool="check_interactions",
                )
            )
        if not out:
            out.append(
                Evidence(
                    id="caution:none",
                    source="curated",
                    kind="note",
                    identifier="no recorded caution",
                    title="Cautions from your record",
                    text=NO_CAUTION_WORDING,
                    structured=True,
                    tool="check_interactions",
                )
            )
        return out

    return [
        get_lab_values,
        get_current_medications,
        search_my_reports,
        search_medical_literature,
        search_health_topics,
        explore_conditions,
        resolve_medicine,
        check_interactions,
    ]
