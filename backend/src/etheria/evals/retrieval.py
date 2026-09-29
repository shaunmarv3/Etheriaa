"""Retrieval eval (M7, spec 15): how well search over a user's own reports finds
the passages that answer a question. No LLM is involved, so it is
deterministic and free.

The corpus is the synthetic fixtures (tests/fixtures/reports/), run through the
real ingestion steps that need no model (parse, PII mask, chunk, BGE embed) and
stored for a throwaway user. Which chunks are relevant is known by
construction (tests/evals/retrieval_queries.yaml explains the rule), so no
model judges relevance.

Four rankings are scored for each question: dense (pgvector cosine), keyword
(Postgres full text), hybrid (the two fused with RRF: what search_my_reports
returns), and hybrid + rerank (the cross-encoder reorders the top 6, as the
chat graph's rerank_evidence does). Metrics: Hit@k, Recall@k, Precision@k, MRR."""

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel
from sqlalchemy import text

from etheria.core.settings import BACKEND_DIR, Settings
from etheria.db.session import Database
from etheria.ingestion.chunking import chunk_pages
from etheria.ingestion.parse import parse_document
from etheria.ingestion.pii_mask import mask_pii
from etheria.ingestion.validation import inspect_upload
from etheria.retrieval.embedding import BgeEmbedder
from etheria.retrieval.hybrid import rankings, rrf
from etheria.retrieval.rerank import CrossEncoderReranker, Reranker

FIXTURES = BACKEND_DIR / "tests" / "fixtures" / "reports"
QUERIES_FILE = BACKEND_DIR / "tests" / "evals" / "retrieval_queries.yaml"
REPORT_FILE = BACKEND_DIR.parent / "docs" / "evals" / "retrieval.md"
RERANK_TOP = 6  # search_my_reports' default k: what rerank_evidence reorders
KS = (1, 3, 5)
CONFIGS = ("dense", "keyword", "hybrid", "hybrid + rerank")
_SPACE = re.compile(r"\s+")


class Query(BaseModel):
    id: str
    query: str
    tests: list[str] = []
    files: list[str] = []
    phrases: list[str] = []


class QuerySet(BaseModel):
    queries: list[Query]


@dataclass(frozen=True)
class Chunk:
    id: str
    filename: str
    content: str


def _norm(s: str) -> str:
    return _SPACE.sub(" ", s).strip().lower()


def load_queries(path: Path = QUERIES_FILE) -> list[Query]:
    return QuerySet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8"))).queries


def lay_ids(path: Path = QUERIES_FILE) -> set[str]:
    """Questions after the '--- lay words ---' marker in the file."""
    body = path.read_text(encoding="utf-8")
    lay = body[body.index("# --- lay words ---") :]
    return set(re.findall(r"\bid: (\w+)", lay))


def relevant(q: Query, chunks: list[Chunk], expected: dict) -> set[str]:
    """The chunk ids that answer `q`, by the rule in the queries file."""
    out = set()
    for c in chunks:
        body = _norm(c.content)
        if q.tests:
            rows = {r["test_name"] for r in expected.get(c.filename, {}).get("lab_rows", [])}
            if any(t in rows and _norm(t) in body for t in q.tests):
                out.add(c.id)
        elif c.filename in q.files and any(_norm(p) in body for p in q.phrases):
            out.add(c.id)
    return out


# ---- metrics ----


def hit_at(ranked: list[str], rel: set[str], k: int) -> float:
    return float(any(i in rel for i in ranked[:k]))


def recall_at(ranked: list[str], rel: set[str], k: int) -> float:
    return len(set(ranked[:k]) & rel) / len(rel)


def precision_at(ranked: list[str], rel: set[str], k: int) -> float:
    return len(set(ranked[:k]) & rel) / k


def reciprocal_rank(ranked: list[str], rel: set[str]) -> float:
    return next((1 / r for r, i in enumerate(ranked, 1) if i in rel), 0.0)


def first_rank(ranked: list[str], rel: set[str]) -> int | None:
    return next((r for r, i in enumerate(ranked, 1) if i in rel), None)


class Scores(BaseModel):
    hit: dict[int, float]
    recall: dict[int, float]
    precision: dict[int, float]
    mrr: float


def score(runs: list[tuple[list[str], set[str]]]) -> Scores:
    n = len(runs)
    return Scores(
        hit={k: sum(hit_at(r, rel, k) for r, rel in runs) / n for k in KS},
        recall={k: sum(recall_at(r, rel, k) for r, rel in runs) / n for k in KS},
        precision={k: sum(precision_at(r, rel, k) for r, rel in runs) / n for k in KS},
        mrr=sum(reciprocal_rank(r, rel) for r, rel in runs) / n,
    )


def reranked(ranked: list[str], scores: list[float]) -> list[str]:
    """The top RERANK_TOP reordered by cross-encoder score; the rest keep their order."""
    head = [
        i for _, i in sorted(zip(scores, ranked[:RERANK_TOP], strict=True), key=lambda x: -x[0])
    ]
    return head + ranked[RERANK_TOP:]


# ---- running ----


async def _build_corpus(
    owner: Database, embedder: BgeEmbedder, expected: dict
) -> tuple[uuid.UUID, list[Chunk]]:
    """A throwaway user holding every text-layer fixture, chunked and embedded
    exactly as ingestion does (parse, mask, chunk, embed)."""
    files = sorted(p for p in FIXTURES.glob("*.pdf"))
    chunks: list[Chunk] = []
    async with owner.system() as s:
        user_id = (
            await s.execute(
                text("INSERT INTO users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
                {"e": f"eval-retrieval-{uuid.uuid4().hex[:10]}@example.com"},
            )
        ).scalar_one()
        for path in files:
            data = path.read_bytes()
            info = inspect_upload(data, path.name)
            pages = parse_document(data, info.mime_type, _no_ocr)
            pages = [p.model_copy(update={"text": mask_pii(p.text).text}) for p in pages]
            drafts = chunk_pages(pages, embedder.count_tokens)
            vectors = await asyncio.to_thread(embedder.embed_documents, [d.content for d in drafts])
            doc_id = (
                await s.execute(
                    text(
                        "INSERT INTO documents (user_id, filename, mime_type, storage_key, sha256, "
                        "size_bytes, page_count, doc_type, status) VALUES (:u, :f, :m, :k, :h, "
                        ":n, :p, :t, 'done') RETURNING id"
                    ),
                    {
                        "u": user_id,
                        "f": path.name,
                        "m": info.mime_type,
                        "k": uuid.uuid4().hex,
                        "h": info.sha256,
                        "n": len(data),
                        "p": info.page_count,
                        "t": expected[path.name]["doc_type"],
                    },
                )
            ).scalar_one()
            for d, vec in zip(drafts, vectors, strict=True):
                chunk_id = (
                    await s.execute(
                        text(
                            "INSERT INTO document_chunks (document_id, user_id, chunk_index, page, "
                            "source_kind, content, embedding) VALUES (:d, :u, :i, :p, :k, :c, "
                            "CAST(:v AS vector)) RETURNING id"
                        ),
                        {
                            "d": doc_id,
                            "u": user_id,
                            "i": d.index,
                            "p": d.page,
                            "k": d.source_kind,
                            "c": d.content,
                            "v": "[" + ",".join(f"{x:.7g}" for x in vec) + "]",
                        },
                    )
                ).scalar_one()
                chunks.append(Chunk(str(chunk_id), path.name, d.content))
    return user_id, chunks


def _no_ocr(_image) -> str:
    return ""  # every fixture in the corpus has a text layer


class QueryRun(BaseModel):
    query: Query
    relevant: int
    ranked: dict[str, list[str]]
    rel_ids: list[str]


async def evaluate(
    db: Database,
    user_id: uuid.UUID,
    chunks: list[Chunk],
    queries: list[Query],
    embedder: BgeEmbedder,
    reranker: Reranker,
    expected: dict,
) -> list[QueryRun]:
    by_id = {c.id: c for c in chunks}
    runs = []
    for q in queries:
        rel = relevant(q, chunks, expected)
        if not rel:
            raise ValueError(f"no chunk is relevant to {q.id}: fix the query or the fixtures")
        vec = await asyncio.to_thread(embedder.embed_query, q.query)
        async with db.for_user(user_id) as s:
            r = await rankings(s, user_id, vec, q.query)
        hybrid = rrf([r.dense, r.keyword])
        scores = await asyncio.to_thread(
            reranker.score, q.query, [by_id[i].content for i in hybrid[:RERANK_TOP]]
        )
        runs.append(
            QueryRun(
                query=q,
                relevant=len(rel),
                ranked={
                    "dense": r.dense,
                    "keyword": r.keyword,
                    "hybrid": hybrid,
                    "hybrid + rerank": reranked(hybrid, scores),
                },
                rel_ids=sorted(rel),
            )
        )
    return runs


def _pct(v: float) -> str:
    return f"{v:.0%}"


def render_report(runs: list[QueryRun], chunks: list[Chunk], lay: set[str], started) -> str:
    docs = len({c.filename for c in chunks})
    lines = [
        "# Retrieval eval",
        "",
        f"Generated by `uv run etheria eval --suite retrieval` on {started:%Y-%m-%d %H:%M} UTC. "
        "No LLM: deterministic and free.",
        "",
        f"Corpus: the {docs} text-layer synthetic reports in `backend/tests/fixtures/reports/`, "
        f"parsed, PII-masked, chunked and embedded (BGE-large) exactly as ingestion does: "
        f"{len(chunks)} chunks for one user. {len(runs)} questions in "
        "`backend/tests/evals/retrieval_queries.yaml`, written by the assistant; "
        f"{sum(r.query.id in lay for r in runs)} ask in everyday words instead of the test name "
        "as printed. "
        "A chunk is relevant when the fixture ground truth says so (the rule is in the "
        "queries file); no model judges relevance.",
        "",
        "Rankings: **dense** (pgvector cosine), **keyword** (Postgres full text), **hybrid** "
        "(both fused with reciprocal rank fusion: what `search_my_reports` returns), "
        f"**hybrid + rerank** (the cross-encoder reorders the top {RERANK_TOP}, as "
        "`rerank_evidence` does in the chat graph).",
        "",
        "| Ranking | Hit@1 | Hit@3 | Hit@5 | Recall@3 | Recall@5 | Precision@3 | MRR |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for config in CONFIGS:
        sc = score([(r.ranked[config], set(r.rel_ids)) for r in runs])
        lines.append(
            f"| {config} | {_pct(sc.hit[1])} | {_pct(sc.hit[3])} | {_pct(sc.hit[5])} | "
            f"{_pct(sc.recall[3])} | {_pct(sc.recall[5])} | {_pct(sc.precision[3])} | "
            f"{sc.mrr:.2f} |"
        )
    lines += [
        "",
        "Precision@3 is capped by how many chunks are relevant: a question with one "
        "relevant chunk scores at most 33%. The corpus is small (one user's reports, "
        f"{len(chunks)} chunks), so a ranking only has to lift one of a few right chunks "
        "to the top; these numbers say little about much larger record sets.",
        "",
        "## By kind of question (MRR)",
        "",
        "| Questions | " + " | ".join(CONFIGS) + " |",
        "|---|" + "---|" * len(CONFIGS),
    ]
    for label, group in (
        ("Test named as printed", [r for r in runs if r.query.id not in lay]),
        ("Lay words", [r for r in runs if r.query.id in lay]),
    ):
        cells = [
            f"{score([(r.ranked[c], set(r.rel_ids)) for r in group]).mrr:.2f}" for c in CONFIGS
        ]
        lines.append(f"| {label} ({len(group)}) | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Per question: rank of the first relevant chunk",
        "",
        "| Question | Relevant chunks | " + " | ".join(CONFIGS) + " |",
        "|---|---|" + "---|" * len(CONFIGS),
    ]
    for r in runs:
        ranks = [first_rank(r.ranked[c], set(r.rel_ids)) for c in CONFIGS]
        cells = [str(x) if x else "not found" for x in ranks]
        kind = " (lay)" if r.query.id in lay else ""
        lines.append(f"| {r.query.query}{kind} | {r.relevant} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


async def run_retrieval_eval(settings: Settings) -> int:
    import json

    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    queries = load_queries()
    embedder, reranker = BgeEmbedder(settings.embedding_model), CrossEncoderReranker()
    print("loading BGE and the cross-encoder ...")
    await asyncio.to_thread(embedder.load)
    await asyncio.to_thread(reranker.load)
    owner, db = Database(settings.sqlalchemy_owner_url), Database(settings.sqlalchemy_url)
    started = datetime.now(UTC)
    user_id = None
    try:
        user_id, chunks = await _build_corpus(owner, embedder, expected)
        runs = await evaluate(db, user_id, chunks, queries, embedder, reranker, expected)
    finally:
        if user_id is not None:
            async with owner.system() as s:
                await s.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
        await owner.dispose()
        await db.dispose()
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(render_report(runs, chunks, lay_ids(), started), encoding="utf-8")
    print(f"wrote {REPORT_FILE}")
    return 0
