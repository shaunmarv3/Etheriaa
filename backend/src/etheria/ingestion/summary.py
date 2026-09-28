"""The document's summary card (spec 5.5), built by code from the classification
and the computed flags, for example: "Full body checkup - Thyrocare - 12 Mar
2026 - 4 abnormal: low haemoglobin, low ferritin, low vitamin D, high LDL"."""

from etheria.ingestion.schemas import Classification, DocType, LabResultRow

_TYPE_LABEL: dict[str, str] = {
    "lab_report": "Lab report",
    "prescription": "Prescription",
    "discharge_summary": "Discharge summary",
    "imaging_report": "Imaging report",
    "other": "Document",
}
MAX_NAMES = 5


def summary_card(c: Classification, rows: list[LabResultRow], doc_type: DocType) -> str:
    parts = [c.title or _TYPE_LABEL[doc_type]]
    if c.lab_name:
        parts.append(c.lab_name)
    if c.report_date:
        parts.append(f"{c.report_date.day} {c.report_date:%b %Y}")
    if doc_type == "lab_report":
        abnormal = [f"{r.flag} {r.test_name.lower()}" for r in rows if r.flag in ("low", "high")]
        if not rows:
            parts.append("no values extracted")
        elif not abnormal:
            parts.append("all values within range")
        else:
            names = abnormal[:MAX_NAMES]
            if len(abnormal) > MAX_NAMES:
                names.append(f"+{len(abnormal) - MAX_NAMES} more")
            parts.append(f"{len(abnormal)} abnormal: " + ", ".join(names))
    return " - ".join(parts)
