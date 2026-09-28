"""Per-type structured extraction (spec 5.5). Only text-layer pages are sent:
numbers are never extracted from OCR'd pages. Lab reports and prescriptions
are extracted one page at a time, so each row's page comes from code rather
than from the model, and grounding later checks exactly that page."""

import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from etheria.ingestion.schemas import (
    DischargeExtraction,
    DocType,
    Extraction,
    ImagingExtraction,
    LabPageExtraction,
    MedicationDraft,
    PagedLabRow,
    PagedMedication,
    PageText,
    PrescriptionExtraction,
)
from etheria.llm.prompts import load_prompt, wrap_document
from etheria.llm.registry import NodeName, StructuredFactory


async def _call(make: StructuredFactory, node: NodeName, schema: type[BaseModel], text: str):
    messages = [SystemMessage(load_prompt(node)), HumanMessage(wrap_document(text))]
    return await make(node, schema).ainvoke(messages)


def _first_page_naming(med: MedicationDraft, pages: list[PageText]) -> int:
    name = " ".join(med.name_raw.split()).casefold()
    for p in pages:
        if name and name in " ".join(p.text.split()).casefold():
            return p.page
    return pages[0].page if pages else 1


async def extract_structured(
    doc_type: DocType, pages: list[PageText], make: StructuredFactory, concurrency: int = 4
) -> Extraction:
    if doc_type == "other":
        return Extraction(doc_type="other")
    text_pages = [p for p in pages if p.source_kind == "text_layer"]
    ext = Extraction(doc_type=doc_type, skipped_ocr_pages=len(pages) - len(text_pages))
    if not text_pages:
        return ext
    sem = asyncio.Semaphore(concurrency)

    async def per_page(node: NodeName, schema: type[BaseModel], p: PageText):
        async with sem:
            return p.page, await _call(make, node, schema, p.text)

    if doc_type == "lab_report":
        results = await asyncio.gather(
            *(per_page("extract_lab_report", LabPageExtraction, p) for p in text_pages)
        )
        ext.lab_rows = [
            PagedLabRow(**row.model_dump(), page=n) for n, out in results for row in out.rows
        ]
    elif doc_type == "prescription":
        results = await asyncio.gather(
            *(per_page("extract_prescription", PrescriptionExtraction, p) for p in text_pages)
        )
        ext.medications = [
            PagedMedication(**m.model_dump(), page=n) for n, out in results for m in out.medications
        ]
    else:
        joined = "\n\n".join(f"[page {p.page}]\n{p.text}" for p in text_pages)
        if doc_type == "discharge_summary":
            out = await _call(make, "extract_discharge_summary", DischargeExtraction, joined)
            ext.details = out.model_dump(exclude={"discharge_medications"})
            ext.medications = [
                PagedMedication(**m.model_dump(), page=_first_page_naming(m, text_pages))
                for m in out.discharge_medications
            ]
        else:
            out = await _call(make, "extract_imaging_report", ImagingExtraction, joined)
            ext.details = out.model_dump()
    return ext
