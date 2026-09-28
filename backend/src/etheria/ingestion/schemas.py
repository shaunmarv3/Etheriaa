"""Data passed between ingestion steps (and, later, Temporal activities)."""

from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Flag = Literal["low", "normal", "high", "unknown"]
SourceKind = Literal["text_layer", "ocr"]


class PageText(BaseModel):
    page: int  # 1-based
    text: str  # PII-masked by the time it leaves the parse activity
    source_kind: SourceKind


class LabRowDraft(BaseModel):
    """One lab row as the model returns it. There is deliberately no flag field:
    the model never decides abnormality (spec 5.6)."""

    test_name: str
    value_text: str
    unit: str | None = None
    ref_range_text: str | None = None


class MedicationDraft(BaseModel):
    name_raw: str
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None


class PagedLabRow(LabRowDraft):
    page: int


class PagedMedication(MedicationDraft):
    page: int


class LabResultRow(BaseModel):
    test_name: str
    value_text: str
    value_numeric: Decimal | None
    unit: str | None
    ref_range_text: str | None
    ref_low: Decimal | None
    ref_high: Decimal | None
    flag: Flag
    page: int


class GroundingStats(BaseModel):
    rows_extracted: int = 0
    rows_dropped_ungrounded: int = 0
    medications_extracted: int = 0
    medications_dropped_ungrounded: int = 0


DocType = Literal["lab_report", "prescription", "discharge_summary", "imaging_report", "other"]


class Classification(BaseModel):
    doc_type: DocType
    title: str | None = None
    report_date: date | None = None
    lab_name: str | None = None
    patient_sex: Literal["male", "female"] | None = None
    confidence: float = Field(ge=0, le=1)


class LabPageExtraction(BaseModel):
    rows: list[LabRowDraft] = []


class PrescriptionExtraction(BaseModel):
    medications: list[MedicationDraft] = []


class DischargeExtraction(BaseModel):
    diagnoses: list[str] = []
    procedures: list[str] = []
    discharge_medications: list[MedicationDraft] = []
    follow_up: str | None = None


class ImagingExtraction(BaseModel):
    modality: str | None = None
    body_part: str | None = None
    findings: str | None = None
    impression: str | None = None


class Extraction(BaseModel):
    doc_type: DocType
    lab_rows: list[PagedLabRow] = []
    medications: list[PagedMedication] = []
    details: dict[str, Any] | None = None  # discharge / imaging: stored as JSONB, display only
    skipped_ocr_pages: int = 0


class ValidatedExtraction(BaseModel):
    lab_results: list[LabResultRow] = []
    medications: list[PagedMedication] = []
    details: dict[str, Any] | None = None
    stats: GroundingStats


class ChunkDraft(BaseModel):
    index: int
    page: int
    source_kind: SourceKind
    content: str


class EmbeddedChunk(ChunkDraft):
    embedding_b64: str  # float32 little-endian (retrieval.embedding.encode_vector)


class IngestInput(BaseModel):
    """Workflow input. Identifiers only: document content never enters
    Temporal's history until it has been PII-masked."""

    document_id: UUID
    user_id: UUID


class IngestOutcome(BaseModel):
    status: Literal["done", "failed", "deleted"]
    error_code: str | None = None
