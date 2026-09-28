import hashlib
import io
import struct
import zlib

import pymupdf
import pytest
from PIL import Image

from etheria.ingestion.validation import (
    MAX_BYTES,
    MAX_PAGES,
    UploadRejected,
    display_filename,
    inspect_upload,
    sniff_mime,
)


def make_pdf(pages: int = 1, text: str = "Haemoglobin 10.9 g/dL") -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def make_png(w: int = 4, h: int = 4) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def png_header_claiming(w: int, h: int) -> bytes:
    """A tiny PNG whose IHDR claims w x h pixels: a decompression bomb's shape."""
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(b"\x00" * 64))
        + _png_chunk(b"IEND", b"")
    )


def rejected(data: bytes, filename: str = "x.pdf") -> str:
    with pytest.raises(UploadRejected) as e:
        inspect_upload(data, filename)
    return e.value.code


def test_pdf_accepted_with_page_count_and_sha() -> None:
    data = make_pdf(pages=2)
    info = inspect_upload(data, "report.pdf")
    assert info.mime_type == "application/pdf"
    assert info.page_count == 2
    assert info.sha256 == hashlib.sha256(data).hexdigest()
    assert info.display_name == "report.pdf"


def test_validation_png_named_pdf_is_png() -> None:
    info = inspect_upload(make_png(), "scan.pdf")
    assert info.mime_type == "image/png"
    assert info.page_count == 1


def test_jpeg_accepted() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="JPEG")
    assert inspect_upload(buf.getvalue(), "a.jpg").mime_type == "image/jpeg"


def test_validation_zip_named_pdf_rejected() -> None:
    assert rejected(b"PK\x03\x04" + b"\x00" * 100) == "unsupported_type"


def test_validation_empty_rejected() -> None:
    assert rejected(b"") == "empty_file"


def test_validation_over_10mb_rejected() -> None:
    assert rejected(b"%PDF-" + b"0" * MAX_BYTES) == "file_too_large"


def test_validation_31_pages_rejected() -> None:
    assert rejected(make_pdf(pages=MAX_PAGES + 1)) == "too_many_pages"
    assert inspect_upload(make_pdf(pages=MAX_PAGES), "ok.pdf").page_count == MAX_PAGES


def test_validation_encrypted_pdf_rejected() -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secret")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    assert rejected(data) == "encrypted_pdf"


def test_validation_pixel_bomb_rejected() -> None:
    assert rejected(png_header_claiming(20000, 20000), "bomb.png") == "image_too_large"


def test_validation_image_over_our_cap_rejected() -> None:
    # 7000 x 7000 = 49 MP: under Pillow's own bomb limit, over ours.
    assert rejected(png_header_claiming(7000, 7000), "big.png") == "image_too_large"


def test_validation_truncated_pdf_rejected() -> None:
    assert rejected(b"%PDF-1.7\n" + b"garbage" * 10) == "corrupt_file"


def test_truncated_png_rejected() -> None:
    assert rejected(make_png()[:40], "cut.png") == "corrupt_file"


def test_sniff_mime() -> None:
    assert sniff_mime(b"%PDF-1.4 ...") == "application/pdf"
    assert sniff_mime(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert sniff_mime(b"\xff\xd8\xff\xe0....") == "image/jpeg"
    assert sniff_mime(b"GIF89a") is None


def test_display_filename_strips_paths_and_controls() -> None:
    assert display_filename("../../etc/pa\x00ss.pdf") == "pass.pdf"
    assert display_filename("C:\\Users\\me\\report.pdf") == "report.pdf"
    assert display_filename(None) == "document"
    assert display_filename("   ") == "document"
    assert len(display_filename("a" * 400 + ".pdf")) <= 255
