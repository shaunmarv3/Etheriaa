"""Report search (spec 5.7, D14): dense + keyword, fused with RRF; the reranker
and the cached query embeddings (spec 8.3)."""

from uuid import UUID, uuid4

import psycopg
from ingestion_fakes import new_user

from etheria.cache.json_cache import JsonCache
from etheria.db.session import Database
from etheria.retrieval.hybrid import rrf, search_reports
from etheria.retrieval.query_cache import CachedQueryEmbedder
from etheria.retrieval.rerank import CrossEncoderReranker


def _unit(i: int) -> list[float]:
    v = [0.0] * 1024
    v[i] = 1.0
    return v


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(str(x) for x in v) + "]"


def _doc_with_chunks(conn: psycopg.Connection, user: UUID, chunks: list[tuple[str, int]]) -> UUID:
    doc = uuid4()
    conn.execute(
        "insert into documents (id, user_id, filename, mime_type, storage_key, sha256, size_bytes, "
        "page_count, doc_type, status) values (%s, %s, 'r.pdf', 'application/pdf', %s, %s, 1, 1, "
        "'lab_report', 'done')",
        (doc, user, uuid4().hex, uuid4().hex),
    )
    for idx, (content, axis) in enumerate(chunks):
        conn.execute(
            "insert into document_chunks (document_id, user_id, chunk_index, page, source_kind, "
            "content, embedding) values (%s, %s, %s, 1, 'text_layer', %s, %s::vector)",
            (doc, user, idx, content, _vec_literal(_unit(axis))),
        )
    return doc


def test_rrf_fuses_two_rankings() -> None:
    fused = rrf([["a", "b", "c"], ["c", "a"]], k=60)
    assert fused[0] == "a"
    assert set(fused) == {"a", "b", "c"}


async def test_hybrid_finds_exact_tokens_and_meaning(db: Database, owner_conn) -> None:
    user, other = new_user(owner_conn), new_user(owner_conn)
    _doc_with_chunks(
        owner_conn,
        user,
        [("HbA1c 8.2 % high, glycated haemoglobin", 5), ("Platelet count within range", 7)],
    )
    _doc_with_chunks(owner_conn, other, [("HbA1c 6.0 % other user", 7)])
    async with db.for_user(user) as s:
        hits = await search_reports(s, user, _unit(7), "HbA1c", k=8)
    contents = [h.content for h in hits]
    assert "HbA1c 8.2 % high, glycated haemoglobin" in contents  # keyword half
    assert "Platelet count within range" in contents  # dense half
    assert all("other user" not in c for c in contents)
    assert all(h.document_id and h.page == 1 for h in hits)


async def test_doc_type_filter(db: Database, owner_conn) -> None:
    user = new_user(owner_conn)
    _doc_with_chunks(owner_conn, user, [("TSH 7.8 high", 3)])
    async with db.for_user(user) as s:
        assert await search_reports(s, user, _unit(3), "TSH", k=8, doc_types=["prescription"]) == []
        assert (
            len(await search_reports(s, user, _unit(3), "TSH", k=8, doc_types=["lab_report"])) == 1
        )


class _DictRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.data[key] = value


class _CountingEmbedder:
    model_name = "fake"
    dim = 1024

    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return _unit(1)


async def test_query_embeddings_are_cached() -> None:
    inner = _CountingEmbedder()
    cached = CachedQueryEmbedder(inner, JsonCache(_DictRedis()))
    assert await cached.embed_query("is my tsh high") == _unit(1)
    assert await cached.embed_query("is my tsh high") == _unit(1)
    assert inner.calls == 1


def test_cross_encoder_prefers_the_relevant_passage() -> None:
    reranker = CrossEncoderReranker()
    scores = reranker.score(
        "What does a high TSH mean?",
        [
            "Mangoes are a popular summer fruit in India.",
            "A high TSH usually means the thyroid gland is underactive (hypothyroidism).",
        ],
    )
    assert scores[1] > scores[0]
