"""Local models load once, even when a warm-up thread and a request race."""

import threading
import time

from etheria.retrieval import embedding, rerank


def test_concurrent_loads_build_the_model_once(monkeypatch) -> None:
    built = []

    class SlowModel:
        def __init__(self, *a, **kw) -> None:
            time.sleep(0.05)
            built.append(1)

        def predict(self, pairs, show_progress_bar=False):
            return [0.0 for _ in pairs]

    import sentence_transformers

    monkeypatch.setattr(sentence_transformers, "CrossEncoder", SlowModel)
    reranker = rerank.CrossEncoderReranker()
    threads = [threading.Thread(target=reranker.load) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert built == [1]


def test_embedder_load_is_guarded() -> None:
    assert isinstance(embedding.BgeEmbedder("x")._lock, type(threading.Lock()))
