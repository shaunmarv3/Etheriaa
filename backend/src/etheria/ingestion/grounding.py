"""The grounding check (spec 5.6): the LLM parses, code judges.

A lab row survives only if its value and every number in its reference range
occur verbatim on the page it came from, after whitespace normalisation. A
number counts only as a whole printed number, so "0.9" is not grounded by
"10.9" and "245000" is not grounded by "2,45,000". Rows that fail are dropped
and counted; the flag is computed here, never taken from the model."""

import re

from etheria.ingestion.labvalues import Sex, compute_flag, parse_number, parse_range
from etheria.ingestion.schemas import GroundingStats, LabResultRow, PagedLabRow, PagedMedication

_NUMBER_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")
# What reports print in the range column when there is no range.
_NO_RANGE = {"-", "--", "---", "–", "—", "na", "n/a", "nil", "none"}


def normalise_ws(s: str) -> str:
    return " ".join(s.split())


def number_tokens(s: str) -> list[str]:
    return [t.rstrip(",") for t in _NUMBER_TOKEN.findall(s)]


def _number_on_page(token: str, page: str) -> bool:
    pattern = rf"(?<![\d.,]){re.escape(token)}(?![\d]|[.,]\d)"
    return re.search(pattern, page) is not None


def _text_on_page(text: str, page: str) -> bool:
    text = normalise_ws(text)
    if not text:
        return False
    if parse_number(text) is not None:
        return _number_on_page(text, page)
    return text in page


def _range_text(text: str | None) -> str | None:
    text = normalise_ws(text or "")
    return None if not text or text.casefold() in _NO_RANGE else text


def is_grounded(row: PagedLabRow, page_text: str) -> bool:
    page = normalise_ws(page_text)
    if not _text_on_page(row.value_text, page):
        return False
    return all(_number_on_page(t, page) for t in number_tokens(row.ref_range_text or ""))


def validate_lab_rows(
    rows: list[PagedLabRow], pages: dict[int, str], sex: Sex | None
) -> tuple[list[LabResultRow], GroundingStats]:
    stats = GroundingStats(rows_extracted=len(rows))
    kept: list[LabResultRow] = []
    for row in rows:
        page_text = pages.get(row.page)
        if page_text is None or not is_grounded(row, page_text):
            stats.rows_dropped_ungrounded += 1
            continue
        value = parse_number(row.value_text)
        range_text = _range_text(row.ref_range_text)
        rng = parse_range(range_text, sex)
        kept.append(
            LabResultRow(
                test_name=normalise_ws(row.test_name),
                value_text=normalise_ws(row.value_text),
                value_numeric=value,
                unit=normalise_ws(row.unit) if row.unit else None,
                ref_range_text=range_text,
                ref_low=rng.low if rng else None,
                ref_high=rng.high if rng else None,
                flag=compute_flag(value, rng),
                page=row.page,
            )
        )
    return kept, stats


def validate_medications(
    meds: list[PagedMedication], pages: dict[int, str], stats: GroundingStats
) -> list[PagedMedication]:
    """A medication name must occur (case-insensitive) on its page: the model
    cannot add a medicine the document does not name."""
    stats.medications_extracted += len(meds)
    kept = []
    for med in meds:
        page = normalise_ws(pages.get(med.page, "")).casefold()
        name = normalise_ws(med.name_raw).casefold()
        if name and name in page:
            kept.append(med)
        else:
            stats.medications_dropped_ungrounded += 1
    return kept
