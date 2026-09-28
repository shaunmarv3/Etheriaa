"""BGE-large-en-v1.5 embeddings on CPU (spec 3.1, D14). Ported from v1's
embedder, with the correct BGE v1.5 query instruction (v1 used a shorter,
wrong one). Documents are embedded without a prefix; queries with it.
Weights live in the Hugging Face cache on the host, never in Docker."""

import base64
import struct
import threading
from typing import Protocol

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DIM = 1024


class Embedder(Protocol):
    dim: int

    def count_tokens(self, text: str) -> int: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class BgeEmbedder:
    dim = DIM

    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()  # a warm-up thread and a request may race

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer  # heavy: import on first use

            model = SentenceTransformer(self.model_name, device="cpu")
            (probe,) = model.encode(["probe"], normalize_embeddings=True)
            if len(probe) != DIM:
                raise RuntimeError(
                    f"{self.model_name} gives {len(probe)} dims; the schema has {DIM}"
                )
            self._model = model

    @property
    def model(self):
        self.load()
        return self._model

    def count_tokens(self, text: str) -> int:
        return len(self.model.tokenizer(text, add_special_tokens=True)["input_ids"])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([QUERY_PREFIX + text])[0]


def encode_vector(v: list[float]) -> str:
    """Compact form for Temporal payloads: base64 of little-endian float32."""
    return base64.b64encode(struct.pack(f"<{len(v)}f", *v)).decode()


def decode_vector(s: str) -> list[float]:
    raw = base64.b64decode(s)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))
