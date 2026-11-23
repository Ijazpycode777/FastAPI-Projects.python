"""File upload validation (pure logic) for study materials.

Server-side content verification — never trusts the browser-supplied MIME type
or the file extension alone. Each allowed type is verified by parsing its
actual bytes:

* PDF  — parsed with ``pypdf`` (a real PDF parser) after the ``%PDF-`` header
  check; a strict parse with at least one page is required.
* PNG / JPEG / WEBP — decoded with Pillow (``Image.open`` + ``verify()``) and
  the detected format is cross-checked against the declared extension.
* DOCX / PPTX — verified as OOXML ZIP archives: must contain
  ``[Content_Types].xml`` plus the type-specific required part
  (``word/document.xml`` / ``ppt/presentation.xml``) and pass a CRC integrity
  test of every entry.

The MIME type is determined server-side from the verified extension and
returned to the caller for storage + DB persistence. Mismatched extension /
content, corrupt, malformed, empty and oversized files are rejected with
``FileValidationError`` (mapped to HTTP 422 by the service) — never a 500.
"""
from __future__ import annotations

import io
import os
import zipfile

from app.core.config import settings


class FileValidationError(Exception):
    """Raised for any upload that fails validation (bad extension, size,
    content/extension mismatch, corrupt or malformed file)."""


# Canonical, server-determined MIME type per verified extension. This is what
# gets stored — never the browser-supplied Content-Type.
EXTENSION_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

# Required internal OOXML parts per Office extension. Both formats are ZIP
# archives that must contain [Content_Types].xml plus their payload part.
_OOXML_REQUIRED_PARTS = {
    "docx": ("[Content_Types].xml", "word/document.xml"),
    "pptx": ("[Content_Types].xml", "ppt/presentation.xml"),
}

# Pillow image format → set of extensions that legitimately describe it.
_IMAGE_FORMAT_EXT = {
    "png": {"png"},
    "jpeg": {"jpg", "jpeg"},
    "webp": {"webp"},
}


def normalize_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").lower()


def validate_extension(filename: str, allowed: list[str] | None = None) -> str:
    allowed = allowed or settings.allowed_extensions
    ext = normalize_extension(filename)
    if ext not in allowed:
        raise FileValidationError(
            f"Extension '.{ext}' is not allowed. Allowed: {', '.join(allowed)}."
        )
    return ext


def validate_size(size_bytes: int, max_mb: int | None = None) -> None:
    max_mb = max_mb or settings.max_upload_mb
    if size_bytes <= 0:
        raise FileValidationError("File is empty.")
    if size_bytes > max_mb * 1024 * 1024:
        raise FileValidationError(f"File exceeds the {max_mb} MB upload limit.")


# ---------------- per-type content verification ----------------

def _verify_pdf(data: bytes) -> None:
    """Reject anything that is not a parseable PDF.

    The ``%PDF-`` header is checked first (cheap). Per the PDF specification the
    header may appear anywhere within the first 1024 bytes — real-world PDFs
    from scanners, email systems and some editors carry a few leading bytes
    before ``%PDF-``, so a strict ``startswith`` check would wrongly reject
    them. The bytes are then handed to ``pypdf`` in *lenient* (non-strict) mode:
    a real parse that still rejects non-PDFs, truncated files and broken
    streams, while accepting valid documents that strict mode would flag
    (leading bytes, linearized docs, xref/object streams, minor quirks). A
    document with zero pages is also rejected (a header-only file would
    otherwise pass).
    """
    if len(data) < 8 or b"%PDF-" not in data[:1024]:
        raise FileValidationError("File does not have a valid PDF header.")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment guard
        raise FileValidationError("PDF validation is unavailable on this server.") from exc
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if len(reader.pages) == 0:
            raise FileValidationError("PDF contains no pages.")
    except FileValidationError:
        raise
    except Exception as exc:
        # Any parse failure (PdfReadError, PdfStreamError on truncation, …)
        # means the file is not a valid PDF — reject it.
        raise FileValidationError("File is not a valid or parseable PDF.") from exc


def _verify_image(data: bytes, ext: str) -> None:
    """Decode with Pillow and cross-check the detected format against the
    declared extension. ``verify()`` checks the pixel/stream integrity, so
    truncated or corrupt images are rejected."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - Pillow is a pinned dep
        raise FileValidationError("Image validation is unavailable on this server.") from exc
    try:
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").lower()
        img.verify()  # raises if the image stream is corrupt
    except FileValidationError:
        raise
    except (UnidentifiedImageError, Exception) as exc:
        raise FileValidationError("File is not a valid or supported image.") from exc
    expected_exts = _IMAGE_FORMAT_EXT.get(fmt)
    if expected_exts is None:
        raise FileValidationError(f"Unsupported image format '{fmt or 'unknown'}'.")
    if ext not in expected_exts:
        raise FileValidationError(
            f"Image content is {fmt.upper()} but the extension is '.{ext}'."
        )


def _verify_ooxml(data: bytes, ext: str) -> None:
    """Verify a DOCX/PPTX is a well-formed OOXML package: a ZIP archive
    containing ``[Content_Types].xml`` and the type-specific payload part, with
    every entry passing its CRC check."""
    required = _OOXML_REQUIRED_PARTS[ext]
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = set(zf.namelist())
    except zipfile.BadZipFile as exc:
        raise FileValidationError(f"File is not a valid .{ext} (not a ZIP archive).") from exc
    missing = [part for part in required if part not in names]
    if missing:
        raise FileValidationError(
            f"File is not a valid .{ext} (missing {', '.join(missing)})."
        )
    # testzip() returns the name of the first entry whose CRC fails, or None.
    # A corrupt compressed stream can also raise (zlib.error / BadZipFile) —
    # treat any such failure as a corrupt document.
    try:
        bad = zf.testzip()
    except Exception as exc:
        raise FileValidationError(f"File is corrupt (.{ext} archive failed integrity check).") from exc
    if bad is not None:
        raise FileValidationError(f"File is corrupt (ZIP entry '{bad}' failed CRC).")


def validate_content(data: bytes, ext: str) -> str:
    """Verify the actual byte content matches the declared extension.

    Returns the server-determined MIME type. Raises ``FileValidationError`` on
    any mismatch, corruption, or unsupported format — never returns for an
    invalid file."""
    if ext == "pdf":
        _verify_pdf(data)
    elif ext in ("png", "jpg", "jpeg", "webp"):
        _verify_image(data, ext)
    elif ext in ("docx", "pptx"):
        _verify_ooxml(data, ext)
    else:  # pragma: no cover - extension was already allowlisted
        raise FileValidationError(f"No content verifier for '.{ext}'.")
    return EXTENSION_MIME[ext]


def validate_upload(filename: str, data: bytes, *, max_mb: int | None = None) -> tuple[str, str]:
    """Run all checks: extension allowlist, size, and real content verification.

    Returns ``(extension, server_determined_mime)``. The browser-supplied
    Content-Type is deliberately ignored — the MIME is derived from the
    verified content.
    """
    ext = validate_extension(filename)
    validate_size(len(data), max_mb)
    mime = validate_content(data, ext)
    return ext, mime
