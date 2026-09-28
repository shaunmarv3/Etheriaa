from decimal import Decimal

from etheria.ingestion.grounding import (
    is_grounded,
    normalise_ws,
    number_tokens,
    validate_lab_rows,
    validate_medications,
)
from etheria.ingestion.schemas import GroundingStats, LabRowDraft, PagedLabRow, PagedMedication

PAGE = (
    "Haemoglobin   10.9 g/dL\n13.0 - 17.0\n"
    "Platelets 2,45,000 /cumm 1,50,000 - 4,10,000\n"
    "Rx: PAN 40 Tablet once daily"
)
PAGES = {1: PAGE}


def row(value: str, rng: str | None = "13.0 - 17.0", name: str = "Haemoglobin", page: int = 1):
    return PagedLabRow(test_name=name, value_text=value, unit="g/dL", ref_range_text=rng, page=page)


def test_normalise_ws() -> None:
    assert normalise_ws("  a \n\t b  ") == "a b"


def test_number_tokens_keep_printed_form() -> None:
    assert number_tokens("1,50,000 - 4,10,000") == ["1,50,000", "4,10,000"]
    assert number_tokens("< 200") == ["200"]


def test_grounded_row_kept_and_flagged() -> None:
    rows, stats = validate_lab_rows([row("10.9")], PAGES, None)
    (r,) = rows
    assert r.flag == "low"
    assert r.value_numeric == Decimal("10.9")
    assert (r.ref_low, r.ref_high) == (Decimal("13.0"), Decimal("17.0"))
    assert r.page == 1
    assert stats.rows_extracted == 1 and stats.rows_dropped_ungrounded == 0


def test_whitespace_normalised() -> None:
    assert is_grounded(row("10.9", rng="13.0  -\n17.0"), PAGE)


def test_invented_value_dropped() -> None:
    rows, stats = validate_lab_rows([row("11.2")], PAGES, None)
    assert rows == []
    assert stats.rows_dropped_ungrounded == 1


def test_substring_of_a_number_is_not_grounded() -> None:
    # "0.9" occurs inside "10.9" but is not a number printed on the page.
    assert not is_grounded(row("0.9"), PAGE)
    assert not is_grounded(row("45,000", rng=None), PAGE)


def test_normalised_number_dropped() -> None:
    r = row("245000", rng="1,50,000 - 4,10,000", name="Platelets")
    rows, stats = validate_lab_rows([r], PAGES, None)
    assert rows == [] and stats.rows_dropped_ungrounded == 1


def test_indian_grouped_value_grounded_and_normal() -> None:
    r = row("2,45,000", rng="1,50,000 - 4,10,000", name="Platelets")
    (out,), _ = validate_lab_rows([r], PAGES, None)
    assert out.value_numeric == Decimal("245000") and out.flag == "normal"


def test_range_number_not_in_text_dropped() -> None:
    rows, stats = validate_lab_rows([row("10.9", rng="13.5 - 17.0")], PAGES, None)
    assert rows == [] and stats.rows_dropped_ungrounded == 1


def test_row_grounded_only_against_its_own_page() -> None:
    pages = {1: PAGE, 2: "Lipid profile LDL 162 mg/dL < 100"}
    rows, stats = validate_lab_rows([row("10.9", page=2)], pages, None)
    assert rows == [] and stats.rows_dropped_ungrounded == 1


def test_unparseable_range_keeps_row_with_unknown_flag() -> None:
    page = "HIV 1 & 2 Antibody Non Reactive Non Reactive"
    r = PagedLabRow(
        test_name="HIV", value_text="Non Reactive", ref_range_text="Non Reactive", page=1
    )
    (out,), _ = validate_lab_rows([r], {1: page}, None)
    assert out.flag == "unknown" and out.value_numeric is None


def test_flag_is_computed_not_trusted() -> None:
    draft = LabRowDraft.model_validate(
        {"test_name": "Hb", "value_text": "10.9", "ref_range_text": "13.0 - 17.0", "flag": "normal"}
    )
    assert not hasattr(draft, "flag")


def test_medication_name_must_occur() -> None:
    stats = GroundingStats()
    meds = [
        PagedMedication(name_raw="Pan 40", page=1),
        PagedMedication(name_raw="Zerodol", page=1),
    ]
    kept = validate_medications(meds, PAGES, stats)
    assert [m.name_raw for m in kept] == ["Pan 40"]
    assert stats.medications_extracted == 2 and stats.medications_dropped_ungrounded == 1
