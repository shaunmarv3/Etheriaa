"""Upload validation (spec 5.1). Runs before anything is stored: the type is
decided by magic bytes, never by the filename or the declared content type."""

import hashlib
import io
import re
import unicodedata
import warnings
from dataclasses import dataclass
from typing import Literal

import pymupdf
from PIL import Image

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 30
MAX_IMAGE_PIXELS = 40_000_000

MimeType = Literal["application/pdf", "image/png", "image/jpeg"]
RejectCode = Literal[
    "file_too_large",
    "unsupported_type",
    "too_many_pages",
    "encrypted_pdf",
    "image_too_large",
    "corrupt_file",
    "empty_file",
]

_MESSAGES: dict[str, str] = {
    "file_too_large": "The file is larger than 10 MB",
    "unsupported_type": "Only PDF, PNG and JPEG files are supported",
    "too_many_pages": f"The document has more than {MAX_PAGES} pages",
    "encrypted_pdf": "Password-protected PDFs are not supported",
    "image_too_large": "The image dimensions are too large",
    "corrupt_file": "The file could not be read",
    "empty_file": "The file is empty",
}


class UploadRejected(Exception):
    def __init__(self, code: RejectCode) -> None:
        super().__init__(_MESSAGES[code])
        self.code: RejectCode = code
        self.message = _MESSAGES[code]


@dataclass(frozen=True)
class UploadInfo:
    mime_type: MimeType
    page_count: int
    sha256: str
    display_name: str


def sniff_mime(data: bytes) -> MimeType | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def display_filename(raw: str | None) -> str:
    """For display only: files are stored under a random key."""
    name = re.split(r"[\\/]", raw or "")[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()
    if not name or name in {".", ".."}:
        return "document"
    if len(name) > 255:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 255 - len(ext) - 1] + dot + ext) if dot and len(ext) <= 10 else name[:255]
    return name


def _pdf_pages(data: bytes) -> int:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise UploadRejected("corrupt_file") from None
    with doc:
        if doc.needs_pass or doc.is_encrypted:
            raise UploadRejected("encrypted_pdf")
        if doc.page_count < 1:
            raise UploadRejected("corrupt_file")
        if doc.page_count > MAX_PAGES:
            raise UploadRejected("too_many_pages")
        return doc.page_count


def _check_image(data: bytes) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data)) as img:
                # Only the header has been read so far: check before decoding anything.
                width, height = img.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise UploadRejected("image_too_large")
                img.verify()
        except UploadRejected:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise UploadRejected("image_too_large") from None
        except Exception:
            raise UploadRejected("corrupt_file") from None


def inspect_upload(data: bytes, filename: str | None) -> UploadInfo:
    if not data:
        raise UploadRejected("empty_file")
    if len(data) > MAX_BYTES:
        raise UploadRejected("file_too_large")
    mime = sniff_mime(data)
    if mime is None:
        raise UploadRejected("unsupported_type")
    if mime == "application/pdf":
        pages = _pdf_pages(data)
    else:
        _check_image(data)
        pages = 1
    return UploadInfo(
        mime_type=mime,
        page_count=pages,
        sha256=hashlib.sha256(data).hexdigest(),
        display_name=display_filename(filename),
    )
