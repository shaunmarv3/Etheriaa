"""Search over the user's report chunks (spec 5.7, D14): pgvector cosine search
and Postgres full-text search, each taking its top 20, fused with reciprocal
rank fusion. Pure embeddings miss exact tokens such as "TSH" or "HbA1c"; pure
keywords miss paraphrases.

The keyword half ORs the query's words (a question such as "is my tsh high"
should not need every word in one chunk) and ranks with ts_rank_cd. Both halves
filter on user_id and run under RLS."""

import re
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PER_LIST = 20
RRF_K = 60
_WORD = re.compile(r"[A-Za-z0-9]+")
_STOP = frozenset(
    "a an and are as at be by can do does for from has have how i in is it its me my of on "
    "or should the this to was what when which why with you your".split()
)


class ChunkHit(BaseModel):
    id: str
    document_id: str
    filename: str
    doc_type: str | None
    report_date: str | None
    page: int | None
    source_kind: str
    content: str
    score: float = 0.0


def rrf_scored(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    return [i for i, _ in rrf_scored(rankings, k)]


def keyword_query(q: str) -> str | None:
    words = [w.lower() for w in _WORD.findall(q) if w.lower() not in _STOP]
    return " | ".join(dict.fromkeys(words)) or None


_COLUMNS = (
    "c.id, c.document_id, d.filename, d.doc_type, d.report_date, c.page, c.source_kind, c.content"
)
_FROM = "FROM document_chunks c JOIN documents d ON d.id = c.document_id"


async def search_reports(
    s: AsyncSession,
    user_id: UUID,
    query_vec: list[float],
    query_text: str,
    k: int = 8,
    doc_types: list[str] | None = None,
) -> list[ChunkHit]:
    type_filter = "AND d.doc_type = ANY(:types) " if doc_types else ""
    params: dict = {"u": user_id, "n": PER_LIST, "types": doc_types or []}
    # pgvector 0.8: keep scanning the HNSW graph until enough rows pass the filter.
    await s.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    dense = await s.execute(
        text(
            f"SELECT {_COLUMNS} {_FROM} "
            f"WHERE c.user_id = :u {type_filter}"
            "ORDER BY c.embedding <=> CAST(:v AS vector) LIMIT :n"
        ),
        {**params, "v": "[" + ",".join(f"{x:.7g}" for x in query_vec) + "]"},
    )
    rows = {str(r.id): r for r in dense}
    rankings = [list(rows)]
    tsq = keyword_query(query_text)
    if tsq:
        keyword = await s.execute(
            text(
                f"SELECT {_COLUMNS} {_FROM} "
                f"WHERE c.user_id = :u {type_filter}"
                "AND c.tsv @@ to_tsquery('simple', :q) "
                "ORDER BY ts_rank_cd(c.tsv, to_tsquery('simple', :q)) DESC LIMIT :n"
            ),
            {**params, "q": tsq},
        )
        ranking = []
        for r in keyword:
            rows.setdefault(str(r.id), r)
            ranking.append(str(r.id))
        rankings.append(ranking)
    return [
        ChunkHit(
            id=i,
            document_id=str(rows[i].document_id),
            filename=rows[i].filename,
            doc_type=rows[i].doc_type,
            report_date=rows[i].report_date.isoformat() if rows[i].report_date else None,
            page=rows[i].page,
            source_kind=rows[i].source_kind,
            content=rows[i].content,
            score=score,
        )
        for i, score in rrf_scored(rankings)[:k]
    ]
