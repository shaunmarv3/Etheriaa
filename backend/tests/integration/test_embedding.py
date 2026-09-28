"""Loads the real BGE-large weights (about 1.3 GB, downloaded once into the
Hugging Face cache on the host)."""

import math

import pytest

from etheria.retrieval.embedding import BgeEmbedder, decode_vector, encode_vector


@pytest.fixture(scope="module")
def embedder() -> BgeEmbedder:
    e = BgeEmbedder("BAAI/bge-large-en-v1.5")
    e.load()
    return e


def test_bge_dim_and_normalised(embedder: BgeEmbedder) -> None:
    (v,) = embedder.embed_documents(["Haemoglobin 10.9 g/dL"])
    assert len(v) == embedder.dim == 1024
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-3)


def test_query_prefix_improves_match(embedder: BgeEmbedder) -> None:
    hb, lipid = embedder.embed_documents(
        [
            "Haemoglobin 10.9 g/dL (13.0 - 17.0), PCV 38.5 %, MCV 85.2 fL",
            "Total Cholesterol 232 mg/dL, LDL Cholesterol 158 mg/dL, HDL 38 mg/dL",
        ]
    )
    q = embedder.embed_query("is my hemoglobin low?")
    dot = lambda a, b: sum(x * y for x, y in zip(a, b, strict=True))  # noqa: E731
    assert dot(q, hb) > dot(q, lipid)


def test_count_tokens_uses_model_tokenizer(embedder: BgeEmbedder) -> None:
    assert embedder.count_tokens("HbA1c") > 2  # word pieces + [CLS]/[SEP]


def test_encode_decode_roundtrip() -> None:
    v = [0.5, -0.25, 1.0]
    assert decode_vector(encode_vector(v)) == v
