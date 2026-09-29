"""Retrieval eval: the metric maths, the relevance rule and the question set."""

import json

import pytest

from etheria.evals.retrieval import (
    FIXTURES,
    Chunk,
    Query,
    first_rank,
    hit_at,
    lay_ids,
    load_queries,
    precision_at,
    recall_at,
    reciprocal_rank,
    relevant,
    reranked,
    score,
)


def test_metrics_on_the_worked_example() -> None:
    # 2 relevant items, 1 found at rank 3 of the top 5
    ranked, rel = ["a", "b", "x", "c", "d"], {"x", "y"}
    assert hit_at(ranked, rel, 5) == 1.0 and hit_at(ranked, rel, 2) == 0.0
    assert recall_at(ranked, rel, 5) == 0.5
    assert precision_at(ranked, rel, 5) == 0.2
    assert reciprocal_rank(ranked, rel) == pytest.approx(1 / 3)
    assert first_rank(ranked, rel) == 3 and first_rank(ranked, {"z"}) is None


def test_scores_average_over_questions() -> None:
    s = score([(["x"], {"x"}), (["a", "x"], {"x"})])
    assert s.hit[1] == 0.5 and s.hit[3] == 1.0 and s.mrr == 0.75


def test_rerank_reorders_only_the_top_six() -> None:
    ranked = [str(i) for i in range(8)]
    out = reranked(ranked, [0, 0, 0, 0, 0, 9])
    assert out[0] == "5" and out[6:] == ["6", "7"] and sorted(out) == sorted(ranked)


def test_relevance_follows_the_ground_truth() -> None:
    expected = {"a.pdf": {"lab_rows": [{"test_name": "TSH"}]}, "b.pdf": {"lab_rows": []}}
    chunks = [
        Chunk("1", "a.pdf", "TSH   7.8 uIU/mL"),
        Chunk("2", "b.pdf", "TSH mentioned in a note"),  # b.pdf has no TSH row
        Chunk("3", "a.pdf", "Free T4 1.1"),
    ]
    assert relevant(Query(id="q", query="tsh", tests=["TSH"]), chunks, expected) == {"1"}
    files = Query(id="f", query="any", files=["b.pdf"], phrases=[""])
    assert relevant(files, chunks, expected) == {"2"}


def test_the_question_set_is_well_formed() -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    tests = {r["test_name"] for v in expected.values() for r in v.get("lab_rows", [])}
    queries = load_queries()
    assert len(queries) >= 30 and len({q.id for q in queries}) == len(queries)
    for q in queries:
        assert bool(q.tests) != bool(q.files), q.id
        assert set(q.tests) <= tests, q.id
        assert set(q.files) <= set(expected) and (not q.files or q.phrases), q.id
    lay = lay_ids()
    assert 10 <= len(lay) < len(queries) and lay <= {q.id for q in queries}
