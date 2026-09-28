"""Per-page text extraction (spec 5.3 step 1), ported from v1's pdf_parser and
image_ocr. A page whose text layer has at least 50 characters uses it;
anything else is OCR'd with Tesseract. `source_kind` records which, because
numbers are never extracted from OCR'd pages (spec 1.3, 5.3 step 4)."""

import io
import shutil
from collections.abc import Callable
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageOps

from etheria.ingestion.schemas import PageText

MIN_TEXT_LAYER_CHARS = 50
OCR_DPI = 300
_WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

OcrFn = Callable[[Image.Image], str]


class OcrUnavailable(Exception):
    """Tesseract is not installed or not where TESSERACT_CMD points."""


def _find_tesseract(tesseract_cmd: str | None) -> str | None:
    if tesseract_cmd:
        return tesseract_cmd if Path(tesseract_cmd).exists() else None
    found = shutil.which("tesseract")
    if found:
        return found
    return str(_WINDOWS_DEFAULT) if _WINDOWS_DEFAULT.exists() else None


def tesseract_ocr(tesseract_cmd: str | None) -> OcrFn:
    """An OCR function. The binary is looked up on first use, so a worker
    without Tesseract still handles text-layer PDFs."""

    def ocr(img: Image.Image) -> str:
        cmd = _find_tesseract(tesseract_cmd)
        if cmd is None:
            raise OcrUnavailable("tesseract not found")
        pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            return pytesseract.image_to_string(_preprocess(img), lang="eng")
        except pytesseract.TesseractNotFoundError as e:
            raise OcrUnavailable(str(e)) from None

    return ocr


def _preprocess(img: Image.Image) -> Image.Image:
    """Greyscale + autocontrast (from v1's image_ocr)."""
    return ImageOps.autocontrast(ImageOps.grayscale(img))


def parse_document(data: bytes, mime_type: str, ocr: OcrFn) -> list[PageText]:
    if mime_type == "application/pdf":
        return _parse_pdf(data, ocr)
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        return [PageText(page=1, text=ocr(img), source_kind="ocr")]


def _parse_pdf(data: bytes, ocr: OcrFn) -> list[PageText]:
    pages: list[PageText] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True)
            if len(text.strip()) >= MIN_TEXT_LAYER_CHARS:
                pages.append(PageText(page=i, text=text, source_kind="text_layer"))
                continue
            pix = page.get_pixmap(dpi=OCR_DPI)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pages.append(PageText(page=i, text=ocr(img), source_kind="ocr"))
    return pages
