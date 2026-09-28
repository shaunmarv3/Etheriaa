from decimal import Decimal

import pytest

from etheria.ingestion.labvalues import RefRange, compute_flag, parse_number, parse_range


def test_parse_number_plain() -> None:
    assert parse_number("10.9") == Decimal("10.9")
    assert parse_number(" 13 ") == Decimal("13")


def test_indian_grouping_number() -> None:
    assert parse_number("1,50,000") == Decimal("150000")
    assert parse_number("2,45,000") == Decimal("245000")
    assert parse_number("12,500") == Decimal("12500")


def test_non_numbers_are_none() -> None:
    for s in ("Positive", "<0.5", "10.9.1", "", "1,5", "-", "Nil"):
        assert parse_number(s) is None, s


def test_indian_grouping_range() -> None:
    r = parse_range("1,50,000 - 4,10,000", None)
    assert r == RefRange(Decimal("150000"), Decimal("410000"), True, True)


def test_plain_range_forms() -> None:
    expected = RefRange(Decimal("13.0"), Decimal("17.0"), True, True)
    assert parse_range("13.0 - 17.0", None) == expected
    assert parse_range("13.0-17.0", None) == expected
    assert parse_range("13.0 to 17.0", None) == expected
    assert parse_range("13.0 – 17.0", None) == expected  # en dash


def test_upper_only_forms() -> None:
    assert parse_range("< 200", None) == RefRange(None, Decimal("200"), True, False)
    for form in ("upto 5.6", "up to 5.6", "Up to 5.6", "<= 5.6", "≤ 5.6"):
        assert parse_range(form, None) == RefRange(None, Decimal("5.6"), True, True), form


def test_lower_only_forms() -> None:
    assert parse_range("> 40", None) == RefRange(Decimal("40"), None, False, True)
    assert parse_range(">= 40", None) == RefRange(Decimal("40"), None, True, True)


def test_sex_specific_ranges() -> None:
    for text in (
        "M: 13.0 - 17.0 F: 12.0 - 15.0",
        "Male 13.0-17.0; Female 12.0-15.0",
        "Male: 13.0 - 17.0\nFemale: 12.0 - 15.0",
    ):
        assert parse_range(text, "male") == RefRange(Decimal("13.0"), Decimal("17.0"), True, True)
        assert parse_range(text, "female") == RefRange(Decimal("12.0"), Decimal("15.0"), True, True)
        assert parse_range(text, None) is None


def test_unparseable_range_is_none() -> None:
    for text in ("See note", "", None, "Negative", "13 - ", "17 - 13"):
        assert parse_range(text, None) is None, text


@pytest.mark.parametrize(
    "value,range_,flag",
    [
        ("10.9", "13.0 - 17.0", "low"),
        ("13.0", "13.0 - 17.0", "normal"),
        ("17.0", "13.0 - 17.0", "normal"),
        ("17.1", "13.0 - 17.0", "high"),
        ("199", "< 200", "normal"),
        ("200", "< 200", "high"),
        ("5.6", "upto 5.6", "normal"),
        ("5.7", "upto 5.6", "high"),
        ("40", "> 40", "low"),
        ("41", "> 40", "normal"),
        ("40", ">= 40", "normal"),
        ("2,45,000", "1,50,000 - 4,10,000", "normal"),
        ("1,20,000", "1,50,000 - 4,10,000", "low"),
        ("Positive", "Negative", "unknown"),
        ("<0.5", "0 - 1", "unknown"),
        ("12", None, "unknown"),
    ],
)
def test_compute_flag(value: str, range_: str | None, flag: str) -> None:
    assert compute_flag(parse_number(value), parse_range(range_, None)) == flag
