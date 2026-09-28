"""Cross-encoder reranking for free-text evidence (spec 4.3 rerank_evidence).

`cross-encoder/ms-marco-MiniLM-L-6-v2` (about 90 MB) reads the question and a
passage together and scores their relevance; it is far faster on CPU than a
large reranker and good enough to order a few dozen passages. Weights load on
first use into the Hugging Face cache on the host, never into Docker."""

import threading
from typing import Protocol

DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()  # a warm-up thread and a request may race

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder  # heavy: import on first use

                self._model = CrossEncoder(self.model_name, device="cpu")

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        self.load()
        scores = self._model.predict([(query, p) for p in passages], show_progress_bar=False)
        return [float(x) for x in scores]
