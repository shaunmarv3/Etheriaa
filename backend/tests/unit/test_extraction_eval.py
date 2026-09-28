from decimal import Decimal

from etheria.ingestion.eval import score_fixture
from etheria.ingestion.schemas import (
    GroundingStats,
    LabResultRow,
    PagedMedication,
    PageText,
    ValidatedExtraction,
)

PAGE = PageText(
    page=1, text="Haemoglobin 12.1 g/dL 13.0 - 17.0\nESR 28 mm/hr 0 - 15", source_kind="text_layer"
)
EXPECTED = {
    "lab_rows": [
        {
            "test_name": "Haemoglobin",
            "value_text": "12.1",
            "unit": "g/dL",
            "ref_range_text": "13.0 - 17.0",
            "flag": "low",
            "page": 1,
        },
        {
            "test_name": "ESR",
            "value_text": "28",
            "unit": "mm/hr",
            "ref_range_text": "0 - 15",
            "flag": "high",
            "page": 1,
        },
    ],
    "medications": [{"name_raw": "Pan 40", "page": 1}],
}


def row(name="Haemoglobin", value="12.1", unit="g/dL", rng="13.0 - 17.0", flag="low"):
    return LabResultRow(
        test_name=name,
        value_text=value,
        value_numeric=Decimal(value),
        unit=unit,
        ref_range_text=rng,
        ref_low=None,
        ref_high=None,
        flag=flag,
        page=1,
    )


def validated(*rows, meds=()):
    return ValidatedExtraction(
        lab_results=list(rows),
        medications=list(meds),
        stats=GroundingStats(rows_extracted=len(rows)),
    )


def test_exact_match_counts_as_recovered() -> None:
    s = score_fixture("x", EXPECTED, validated(row()), [PAGE])
    assert (s.expected_rows, s.recovered_rows, s.extra_rows) == (2, 1, 0)
    assert s.misses == ["ESR: missing"]


def test_unit_mismatch_is_not_recovered() -> None:
    s = score_fixture("x", EXPECTED, validated(row(unit="mg/dL")), [PAGE])
    assert s.recovered_rows == 0


def test_unit_case_and_range_whitespace_ignored() -> None:
    s = score_fixture("x", EXPECTED, validated(row(unit="G/DL", rng="13.0  -  17.0")), [PAGE])
    assert s.recovered_rows == 1


def test_wrong_flag_is_not_recovered() -> None:
    s = score_fixture("x", EXPECTED, validated(row(flag="normal")), [PAGE])
    assert s.recovered_rows == 0


def test_test_name_punctuation_and_case_ignored() -> None:
    s = score_fixture("x", EXPECTED, validated(row(name="HAEMOGLOBIN.")), [PAGE])
    assert s.recovered_rows == 1


def test_extra_rows_counted_not_penalised() -> None:
    s = score_fixture("x", EXPECTED, validated(row(), row(name="MCV", value="85.2")), [PAGE])
    assert (s.recovered_rows, s.extra_rows) == (1, 1)


def test_stored_values_regrounded() -> None:
    s = score_fixture("x", EXPECTED, validated(row(value="99.9")), [PAGE])
    assert s.stored_values_grounded is False


def test_medications_matched_by_name() -> None:
    meds = [PagedMedication(name_raw="PAN 40", page=1)]
    s = score_fixture("x", EXPECTED, validated(meds=meds), [PAGE])
    assert (s.expected_medications, s.recovered_medications) == (1, 1)
