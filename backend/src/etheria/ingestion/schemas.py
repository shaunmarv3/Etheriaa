"""Data passed between ingestion steps (and, later, Temporal activities)."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

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
