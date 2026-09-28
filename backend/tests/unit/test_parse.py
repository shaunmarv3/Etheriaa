import io
import shutil
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from etheria.ingestion.parse import OcrUnavailable, parse_document, tesseract_ocr

REPORTS = Path(__file__).resolve().parents[1] / "fixtures" / "reports"
TESSERACT = shutil.which("tesseract") or (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").exists()
    else None
)


class FakeOcr:
    def __init__(self, text: str = "OCR TEXT Haemoglobin 12.1") -> None:
        self.text = text
        self.calls = 0

    def __call__(self, img: Image.Image) -> str:
        self.calls += 1
        assert img.width > 100 and img.height > 100
        return self.text


def pdf_with(pages: list[str | None]) -> bytes:
    """None = an image-only page (no text layer)."""
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text is None:
            buf = io.BytesIO()
            Image.new("RGB", (400, 200), "white").save(buf, format="PNG")
            page.insert_image(pymupdf.Rect(72, 72, 472, 272), stream=buf.getvalue())
        else:
            page.insert_textbox(pymupdf.Rect(72, 72, 520, 770), text, fontsize=9)
    return doc.tobytes()


def test_text_layer_pages_use_text_layer() -> None:
    ocr = FakeOcr()
    pages = parse_document((REPORTS / "lab_fullbody.pdf").read_bytes(), "application/pdf", ocr)
    assert [p.page for p in pages] == [1, 2, 3]
    assert {p.source_kind for p in pages} == {"text_layer"}
    assert ocr.calls == 0
    assert "Vitamin D (25-OH)" in pages[2].text


def test_blank_pdf_page_goes_to_ocr() -> None:
    ocr = FakeOcr()
    pages = parse_document(pdf_with(["Haemoglobin 12.1 g/dL " * 5, None]), "application/pdf", ocr)
    assert [p.source_kind for p in pages] == ["text_layer", "ocr"]
    assert pages[1].text == ocr.text
    assert ocr.calls == 1


def test_short_text_layer_goes_to_ocr() -> None:
    ocr = FakeOcr()
    (page,) = parse_document(pdf_with(["x" * 49]), "application/pdf", ocr)
    assert page.source_kind == "ocr"
    (page,) = parse_document(pdf_with(["x" * 50]), "application/pdf", FakeOcr())
    assert page.source_kind == "text_layer"


def test_scan_pages_are_ocr() -> None:
    ocr = FakeOcr()
    pages = parse_document((REPORTS / "lab_cbc_scan.png").read_bytes(), "image/png", ocr)
    assert len(pages) == 1
    assert pages[0].source_kind == "ocr"
    assert pages[0].text == ocr.text


def test_ocr_unavailable_raises() -> None:
    ocr = tesseract_ocr("C:/nope/tesseract.exe")
    with pytest.raises(OcrUnavailable):
        ocr(Image.new("L", (200, 200), 255))


@pytest.mark.skipif(TESSERACT is None, reason="Tesseract not installed")
def test_real_ocr_reads_scan() -> None:
    pages = parse_document(
        (REPORTS / "lab_cbc_scan.png").read_bytes(), "image/png", tesseract_ocr(None)
    )
    assert "haemoglobin" in pages[0].text.lower()
