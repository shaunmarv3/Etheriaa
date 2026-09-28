"""Fakes and helpers for ingestion tests (tests/ is on sys.path)."""

import asyncio
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from langchain_core.runnables import RunnableLambda

from etheria.ingestion.schemas import (
    Classification,
    DischargeExtraction,
    ImagingExtraction,
    LabPageExtraction,
    LabRowDraft,
    PrescriptionExtraction,
)

REPORTS = Path(__file__).resolve().parent / "fixtures" / "reports"
EXPECTED = json.loads((REPORTS / "expected.json").read_text(encoding="utf-8"))


def new_user(owner_conn: psycopg.Connection) -> UUID:
    row = owner_conn.execute(
        "insert into users (email, password_hash) values (%s, 'x') returning id",
        (f"{uuid4().hex[:12]}@example.com",),
    ).fetchone()
    assert row is not None
    return row[0]


class FakeEmbedder:
    """Deterministic unit vectors; tokens = whitespace words."""

    dim = 1024

    def __init__(self, gate: asyncio.Event | None = None) -> None:
        self.calls = 0

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def _vec(self, text: str) -> list[float]:
        seed = hashlib.sha256(text.encode()).digest()
        raw = [seed[i % 32] - 127.5 for i in range(self.dim)]
        norm = math.sqrt(sum(x * x for x in raw))
        return [x / norm for x in raw]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FixtureModels:
    """A structured-model factory answering from expected.json, as a perfect
    model would. `fail` makes every call to that node raise."""

    def __init__(self, fixture: str, fail: str | None = None) -> None:
        self.exp = EXPECTED[fixture]
        self.fail = fail
        self.calls: dict[str, int] = {}

    def _answer(self, node: str, messages: list[Any]) -> Any:
        self.calls[node] = self.calls.get(node, 0) + 1
        if node == self.fail:
            raise RuntimeError(f"{node} upstream error")
        exp = self.exp
        if node == "classify_document":
            return Classification(
                doc_type=exp["doc_type"],
                title="Test report",
                lab_name=exp.get("lab_name"),
                patient_sex=exp["sex"],
                confidence=0.95,
            )
        text = messages[-1].content
        if node == "extract_lab_report":
            rows = [
                LabRowDraft(
                    **{k: r[k] for k in ("test_name", "value_text", "unit", "ref_range_text")}
                )
                for r in exp["lab_rows"]
                if r["value_text"] in text and r["test_name"] in text
            ]
            return LabPageExtraction(rows=rows)
        if node == "extract_prescription":
            return PrescriptionExtraction(medications=exp["medications"])
        if node == "extract_discharge_summary":
            return DischargeExtraction(
                diagnoses=["Community acquired pneumonia"], discharge_medications=exp["medications"]
            )
        return ImagingExtraction()

    def __call__(self, node, schema):
        async def run(messages):
            return self._answer(node, messages)

        return RunnableLambda(run)


class FakeOcr:
    def __init__(
        self, text: str = "Haemoglobin 12.1 g/dL scanned text", fail: Exception | None = None
    ):
        self.text = text
        self.fail = fail
        self.calls = 0

    def __call__(self, img) -> str:
        self.calls += 1
        if self.fail:
            raise self.fail
        return self.text
