from datetime import date
from decimal import Decimal

from etheria.ingestion.schemas import Classification, LabResultRow
from etheria.ingestion.summary import summary_card


def lab(name: str, flag: str) -> LabResultRow:
    return LabResultRow(
        test_name=name,
        value_text="1",
        value_numeric=Decimal(1),
        unit=None,
        ref_range_text=None,
        ref_low=None,
        ref_high=None,
        flag=flag,
        page=1,
    )


CLS = Classification(
    doc_type="lab_report",
    title="Full body checkup",
    lab_name="Northwind",
    report_date=date(2026, 3, 12),
    confidence=0.9,
)


def test_lab_summary_lists_abnormal_names() -> None:
    rows = [
        lab("Haemoglobin", "low"),
        lab("Ferritin", "low"),
        lab("TSH", "normal"),
        lab("LDL Cholesterol", "high"),
        lab("HIV", "unknown"),
    ]
    assert summary_card(CLS, rows, "lab_report") == (
        "Full body checkup - Northwind - 12 Mar 2026 - "
        "3 abnormal: low haemoglobin, low ferritin, high ldl cholesterol"
    )


def test_all_normal_summary() -> None:
    assert summary_card(CLS, [lab("TSH", "normal")], "lab_report").endswith(
        "- all values within range"
    )


def test_lab_report_without_rows() -> None:
    assert summary_card(CLS, [], "lab_report").endswith("- no values extracted")


def test_missing_date_and_lab_omitted() -> None:
    c = Classification(doc_type="prescription", confidence=0.9)
    assert summary_card(c, [], "prescription") == "Prescription"


def test_title_falls_back_to_type_label() -> None:
    c = Classification(doc_type="discharge_summary", report_date=date(2026, 3, 9), confidence=0.9)
    assert summary_card(c, [], "discharge_summary") == "Discharge summary - 9 Mar 2026"


def test_more_than_five_abnormal_truncated() -> None:
    rows = [lab(f"T{i}", "high") for i in range(8)]
    card = summary_card(CLS, rows, "lab_report")
    assert card.endswith("8 abnormal: high t0, high t1, high t2, high t3, high t4, +3 more")
