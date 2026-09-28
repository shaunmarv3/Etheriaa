"""rerank_evidence (spec 4.3): the join after retrieval_agent || triage.
Dedupe; keep all structured evidence (lab rows, interactions, cautions,
condition matches) plus the user's abnormal lab snapshot; rerank free-text
passages with the cross-encoder and cut them to the token budget; number the
result for citations. If the reranker fails, retrieval order is kept."""

import asyncio
import math

from etheria.graph.deps import GraphDeps
from etheria.graph.nodes.common import Timer, lab_line, log
from etheria.graph.schemas import Evidence, TurnData
from etheria.graph.state import ChatState

CHARS_PER_TOKEN = 4


def snapshot_evidence(turn: TurnData) -> list[Evidence]:
    return [
        Evidence(
            id=f"lab:{f.id}",
            source="user_document",
            kind="lab",
            identifier=f.document_id,
            title=f"Your report {f.filename}" + (f", {f.report_date}" if f.report_date else ""),
            text=lab_line(f),
            structured=True,
            tool="load_context",
        )
        for f in turn.lab_snapshot
    ]


def select(
    evidence: list[Evidence], scores: list[float] | None, budget_tokens: int
) -> list[Evidence]:
    seen: set[str] = set()
    unique = []
    for e in evidence:
        if e.id not in seen:
            seen.add(e.id)
            unique.append(e)
    structured = [e for e in unique if e.structured]
    free = [e for e in unique if not e.structured]
    if scores is not None:
        free = [
            e.model_copy(update={"relevance": 1 / (1 + math.exp(-s))})
            for e, s in sorted(zip(free, scores, strict=True), key=lambda p: -p[1])
        ]
    budget = budget_tokens * CHARS_PER_TOKEN - sum(len(e.text) for e in structured)
    kept = []
    for e in free:
        if len(e.text) > budget:
            continue
        kept.append(e)
        budget -= len(e.text)
    return [e.model_copy(update={"n": i}) for i, e in enumerate(structured + kept, start=1)]


def make_rerank(deps: GraphDeps):
    async def rerank_evidence(state: ChatState) -> dict:
        timer = Timer()
        turn = state["turn"]
        evidence = turn.evidence + snapshot_evidence(turn)
        free = [e for e in {e.id: e for e in evidence}.values() if not e.structured]
        query = turn.understanding.search_query if turn.understanding else turn.user_message
        scores = None
        if free and deps.reranker is not None:
            try:
                scores = await asyncio.to_thread(
                    deps.reranker.score, query or turn.user_message, [e.text for e in free]
                )
            except Exception as e:
                log.warning("rerank_failed", error=type(e).__name__)
        # select() dedupes the same way, so scores line up with `free`.
        ranked = select(evidence, scores, deps.evidence_budget_tokens)
        entry = timer.entry(
            "rerank_evidence",
            "evidence",
            f"{len(ranked)} of {len(evidence)} items kept",
            reranked=scores is not None,
        )
        return {"turn": {"evidence": ranked, "trace": [entry]}}

    return rerank_evidence
