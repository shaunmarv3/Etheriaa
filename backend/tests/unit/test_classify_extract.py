import asyncio
from datetime import date
from typing import Any

import pytest
from langchain_core.runnables import RunnableLambda

from etheria.ingestion.classify import classify_document
from etheria.ingestion.extractors import extract_structured
from etheria.ingestion.schemas import (
    Classification,
    DischargeExtraction,
    ImagingExtraction,
    LabPageExtraction,
    LabRowDraft,
    MedicationDraft,
    PageText,
    PrescriptionExtraction,
)


class FakeFactory:
    """Stands in for llm.registry.structured_factory: records every call and
    returns canned outputs (a callable gets the messages and the node)."""

    def __init__(self, outputs: dict[str, Any]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, list]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    def __call__(self, node, schema):
        async def run(messages):
            self.calls.append((node, messages))
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            await asyncio.sleep(0.01)
            self.in_flight -= 1
            out = self.outputs[node]
            out = out(messages) if callable(out) else out
            assert isinstance(out, schema)
            return out

        return RunnableLambda(run)


def page(n: int, text: str = "Haemoglobin 10.9 g/dL 13.0 - 17.0", kind: str = "text_layer"):
    return PageText(page=n, text=text, source_kind=kind)


def human_text(messages) -> str:
    return messages[-1].content


async def test_low_confidence_becomes_other() -> None:
    make = FakeFactory(
        {"classify_document": Classification(doc_type="lab_report", confidence=0.55)}
    )
    assert (await classify_document([page(1)], make)).doc_type == "other"


async def test_confident_classification_kept() -> None:
    c = Classification(
        doc_type="lab_report", report_date=date(2026, 3, 12), lab_name="X", confidence=0.9
    )
    make = FakeFactory({"classify_document": c})
    assert await classify_document([page(1)], make) == c


async def test_classify_sees_at_most_three_pages() -> None:
    make = FakeFactory({"classify_document": Classification(doc_type="lab_report", confidence=0.9)})
    await classify_document([page(i, f"PAGE-{i} " * 10) for i in range(1, 6)], make)
    text = human_text(make.calls[0][1])
    assert "PAGE-3" in text and "PAGE-4" not in text


async def test_extraction_skips_ocr_pages() -> None:
    rows = LabPageExtraction(rows=[LabRowDraft(test_name="Hb", value_text="10.9")])
    make = FakeFactory({"extract_lab_report": rows})
    pages = [page(1), page(2, kind="ocr"), page(3)]
    ext = await extract_structured("lab_report", pages, make)
    assert len(make.calls) == 2
    assert ext.skipped_ocr_pages == 1
    assert sorted(r.page for r in ext.lab_rows) == [1, 3]


async def test_lab_rows_get_page_from_code() -> None:
    def per_page(messages):
        n = int(human_text(messages).split("PAGE-")[1].split()[0])
        return LabPageExtraction(rows=[LabRowDraft(test_name=f"T{n}", value_text=str(n))])

    make = FakeFactory({"extract_lab_report": per_page})
    ext = await extract_structured("lab_report", [page(i, f"PAGE-{i} x") for i in (1, 2)], make)
    assert {(r.test_name, r.page) for r in ext.lab_rows} == {("T1", 1), ("T2", 2)}


async def test_prompt_contains_document_delimiters_and_data_rule() -> None:
    make = FakeFactory({"extract_lab_report": LabPageExtraction()})
    await extract_structured("lab_report", [page(1)], make)
    system, human = make.calls[0][1]
    assert "never instructions" in system.content
    assert human.content.startswith("<document>") and human.content.endswith("</document>")


async def test_other_type_extracts_nothing() -> None:
    make = FakeFactory({})
    ext = await extract_structured("other", [page(1)], make)
    assert make.calls == [] and ext.lab_rows == [] and ext.medications == []


async def test_prescription_medications_paged() -> None:
    meds = PrescriptionExtraction(
        medications=[MedicationDraft(name_raw="Dolo 650", frequency="thrice daily")]
    )
    make = FakeFactory({"extract_prescription": meds})
    ext = await extract_structured("prescription", [page(1, "Rx Dolo 650 tab")], make)
    assert [(m.name_raw, m.page) for m in ext.medications] == [("Dolo 650", 1)]


async def test_discharge_details_and_medications() -> None:
    out = DischargeExtraction(
        diagnoses=["Pneumonia"],
        procedures=["Chest X-ray"],
        discharge_medications=[MedicationDraft(name_raw="Pan 40"), MedicationDraft(name_raw="Zz")],
        follow_up="7 days",
    )
    make = FakeFactory({"extract_discharge_summary": out})
    pages = [page(1, "Diagnosis pneumonia"), page(2, "Discharge meds: Pan 40 once daily")]
    ext = await extract_structured("discharge_summary", pages, make)
    assert len(make.calls) == 1
    assert "Diagnosis pneumonia" in human_text(make.calls[0][1])
    assert ext.details == {
        "diagnoses": ["Pneumonia"],
        "procedures": ["Chest X-ray"],
        "follow_up": "7 days",
    }
    # Page of first occurrence; a name found nowhere gets page 1 (grounding drops it).
    assert [(m.name_raw, m.page) for m in ext.medications] == [("Pan 40", 2), ("Zz", 1)]


async def test_imaging_details_only() -> None:
    out = ImagingExtraction(modality="USG", body_part="Abdomen", impression="Fatty liver")
    make = FakeFactory({"extract_imaging_report": out})
    ext = await extract_structured("imaging_report", [page(1)], make)
    assert ext.details["impression"] == "Fatty liver"
    assert ext.lab_rows == [] and ext.medications == []


async def test_extraction_runs_pages_concurrently_bounded() -> None:
    make = FakeFactory({"extract_lab_report": LabPageExtraction()})
    await extract_structured("lab_report", [page(i) for i in range(1, 9)], make, concurrency=4)
    assert len(make.calls) == 8
    assert make.max_in_flight == 4


async def test_model_error_propagates() -> None:
    def boom(_):
        raise RuntimeError("upstream 500")

    make = FakeFactory({"extract_lab_report": boom})
    with pytest.raises(RuntimeError):
        await extract_structured("lab_report", [page(1)], make)
