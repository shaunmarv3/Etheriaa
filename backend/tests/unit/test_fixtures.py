"""The synthetic fixtures (tests/fixtures/reports) are the extraction eval's
ground truth: check they are consistent before trusting any score."""

import json
from pathlib import Path

import pymupdf

from etheria.ingestion.grounding import normalise_ws, number_tokens
from etheria.ingestion.parse import parse_document
from etheria.ingestion.pii_mask import mask_pii

REPORTS = Path(__file__).resolve().parents[1] / "fixtures" / "reports"
EXPECTED = json.loads((REPORTS / "expected.json").read_text(encoding="utf-8"))


def test_expected_json_matches_files() -> None:
    on_disk = {p.name for p in REPORTS.iterdir() if p.suffix in {".pdf", ".png"}}
    assert on_disk == set(EXPECTED)


def test_every_expected_value_is_in_pdf_text() -> None:
    for name, exp in EXPECTED.items():
        if not exp["text_layer"]:
            continue
        doc = pymupdf.open(REPORTS / name)
        for row in exp["lab_rows"]:
            page = normalise_ws(doc[row["page"] - 1].get_text("text", sort=True))
            assert row["value_text"] in page, (name, row)
            for token in number_tokens(row["ref_range_text"] or ""):
                assert token in page, (name, row)
        for med in exp["medications"]:
            assert med["name_raw"] in doc[med["page"] - 1].get_text("text", sort=True), name


def test_pii_is_masked_in_every_fixture() -> None:
    for name, exp in EXPECTED.items():
        if not exp["text_layer"]:
            continue
        mime = "image/png" if name.endswith(".png") else "application/pdf"
        pages = parse_document((REPORTS / name).read_bytes(), mime, lambda _img: "")
        masked = "\n".join(mask_pii(p.text).text for p in pages)
        for secret in exp["pii"]:
            assert secret not in masked, (name, secret)
        assert "Age/Sex" in masked


def test_fixture_rows_cover_the_range_forms() -> None:
    ranges = {r["ref_range_text"] for e in EXPECTED.values() for r in e["lab_rows"]}
    assert any(r and r.startswith("<") for r in ranges)
    assert any(r and r.startswith(">") for r in ranges)
    assert any(r and r.startswith("upto") for r in ranges)
    assert any(r and "M:" in r for r in ranges)
    assert any(r and "," in r for r in ranges)
    assert None in ranges


def test_injected_fixture_prints_the_injection() -> None:
    doc = pymupdf.open(REPORTS / "lab_injected.pdf")
    assert "ignore previous instructions" in doc[0].get_text()
