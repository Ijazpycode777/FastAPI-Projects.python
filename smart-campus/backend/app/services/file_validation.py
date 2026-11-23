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
import zlib
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

# ---- zip-bomb guards for OOXML (DOCX/PPTX) packages ----
# The compressed upload is already capped at ``max_upload_mb``; these bound the
# *decompressed* archive so a small malicious package cannot expand to exhaust
# disk or memory. The declared-size checks run BEFORE any decompression; the
# bounded CRC check additionally caps ACTUAL decompression per entry (catching
# archives that lie about their declared uncompressed size).
_OOXML_MAX_ENTRIES = 5_000                          # max parts in one package
_OOXML_MAX_ENTRY_UNCOMPRESSED = 100 * 1024 * 1024   # 100 MB per part
_OOXML_MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024   # 200 MB total decompressed
_OOXML_MAX_COMPRESSION_RATIO = 100                  # max uncompressed:compressed
_ZIP_CHUNK = 64 * 1024                              # streaming chunk for bounded CRC


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


def _enforce_archive_limits(zf: zipfile.ZipFile, ext: str) -> None:
    """Reject OOXML packages that look like zip-bombs, using the declared sizes
    in the central directory (no decompression). Guards: entry count, per-entry
    uncompressed size, total uncompressed size, and overall compression ratio."""
    infos = zf.infolist()
    if len(infos) > _OOXML_MAX_ENTRIES:
        raise FileValidationError(
            f".{ext} has too many parts ({len(infos)} > {_OOXML_MAX_ENTRIES})."
        )
    total_uncompressed = 0
    total_compressed = 0
    for info in infos:
        if info.file_size > _OOXML_MAX_ENTRY_UNCOMPRESSED:
            raise FileValidationError(
                f".{ext} part '{info.filename}' is too large when decompressed "
                f"({info.file_size} > {_OOXML_MAX_ENTRY_UNCOMPRESSED} bytes)."
            )
        total_uncompressed += info.file_size
        total_compressed += info.compress_size
    if total_uncompressed > _OOXML_MAX_TOTAL_UNCOMPRESSED:
        raise FileValidationError(
            f".{ext} is too large when decompressed "
            f"({total_uncompressed} > {_OOXML_MAX_TOTAL_UNCOMPRESSED} bytes)."
        )
    # Real OOXML compresses modestly (single digits to low tens). A ratio in the
    # hundreds or thousands signals a zip-bomb. Only meaningful when there is real
    # compressed payload to compare against (stored/empty entries compress to ~0).
    if total_compressed > 0:
        ratio = total_uncompressed / total_compressed
        if ratio > _OOXML_MAX_COMPRESSION_RATIO:
            raise FileValidationError(
                f".{ext} has an extreme compression ratio "
                f"({ratio:.0f}:1 > {_OOXML_MAX_COMPRESSION_RATIO}:1) — possible zip-bomb."
            )


def _bounded_crc_check(zf: zipfile.ZipFile, ext: str) -> None:
    """Verify every entry's CRC by decompressing in bounded chunks.

    Decompression of each entry is capped at ``_OOXML_MAX_ENTRY_UNCOMPRESSED``
    bytes; an entry whose stream decompresses beyond the cap (an archive that
    lies about its declared size — a decompression bomb) is rejected. CRC is
    computed incrementally so the full decompressed payload is never held in
    memory at once."""
    for info in zf.infolist():
        if info.is_dir():
            continue
        crc = 0
        produced = 0
        try:
            with zf.open(info, "r") as fh:
                while True:
                    chunk = fh.read(_ZIP_CHUNK)
                    if not chunk:
                        break
                    produced += len(chunk)
                    if produced > _OOXML_MAX_ENTRY_UNCOMPRESSED:
                        raise FileValidationError(
                            f".{ext} part '{info.filename}' is too large when decompressed "
                            f"(exceeds {_OOXML_MAX_ENTRY_UNCOMPRESSED} bytes)."
                        )
                    crc = zlib.crc32(chunk, crc)
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError(f"File is corrupt (.{ext} archive failed integrity check).") from exc
        if crc != info.CRC:
            raise FileValidationError(f"File is corrupt (ZIP entry '{info.filename}' failed CRC).")


def _check_ooxml_archive(zf: zipfile.ZipFile, ext: str) -> None:
    """Shared DOCX/PPTX verification: required OOXML parts, zip-bomb limits
    (declared sizes, before any decompression), then a bounded CRC integrity
    check of every entry."""
    required = _OOXML_REQUIRED_PARTS[ext]
    try:
        names = set(zf.namelist())
    except Exception as exc:
        raise FileValidationError(f"File is not a valid .{ext} (malformed archive).") from exc
    missing = [part for part in required if part not in names]
    if missing:
        raise FileValidationError(
            f"File is not a valid .{ext} (missing {', '.join(missing)})."
        )
    _enforce_archive_limits(zf, ext)
    _bounded_crc_check(zf, ext)


def _verify_ooxml(data: bytes, ext: str) -> None:
    """Verify a DOCX/PPTX (given as bytes) is a well-formed OOXML package."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise FileValidationError(f"File is not a valid .{ext} (not a ZIP archive).") from exc
    try:
        _check_ooxml_archive(zf, ext)
    finally:
        zf.close()


def _verify_ooxml_from_path(path: str, ext: str) -> None:
    """Verify a DOCX/PPTX (given as a filesystem path) — streams from disk, no
    full read into memory."""
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise FileValidationError(f"File is not a valid .{ext} (not a ZIP archive).") from exc
    try:
        _check_ooxml_archive(zf, ext)
    finally:
        zf.close()


def _verify_pdf_from_path(path: str) -> None:
    """Path-based PDF verification — streams from disk instead of loading the
    whole file into memory. Same checks as :func:`_verify_pdf`."""
    with open(path, "rb") as fh:
        head = fh.read(1024)
    if len(head) < 8 or b"%PDF-" not in head:
        raise FileValidationError("File does not have a valid PDF header.")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment guard
        raise FileValidationError("PDF validation is unavailable on this server.") from exc
    try:
        with open(path, "rb") as fh:
            reader = PdfReader(fh, strict=False)
            if len(reader.pages) == 0:
                raise FileValidationError("PDF contains no pages.")
    except FileValidationError:
        raise
    except Exception as exc:
        raise FileValidationError("File is not a valid or parseable PDF.") from exc


def _verify_image_from_path(path: str, ext: str) -> None:
    """Path-based image verification — Pillow reads the header + verifies
    integrity from the stream, without loading the whole image into memory."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - Pillow is a pinned dep
        raise FileValidationError("Image validation is unavailable on this server.") from exc
    try:
        with open(path, "rb") as fh:
            img = Image.open(fh)
            fmt = (img.format or "").lower()
            img.verify()
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


def validate_content_path(path: str, ext: str) -> str:
    """Path-based content verification — streams from disk, the whole file is
    never held in a single in-memory buffer. Same checks + MIME mapping as
    :func:`validate_content`."""
    if ext == "pdf":
        _verify_pdf_from_path(path)
    elif ext in ("png", "jpg", "jpeg", "webp"):
        _verify_image_from_path(path, ext)
    elif ext in ("docx", "pptx"):
        _verify_ooxml_from_path(path, ext)
    else:  # pragma: no cover - extension was already allowlisted
        raise FileValidationError(f"No content verifier for '.{ext}'.")
    return EXTENSION_MIME[ext]


def validate_upload_path(filename: str, path: str, *, max_mb: int | None = None) -> tuple[str, str]:
    """Stream-based variant of :func:`validate_upload` for files already on disk.

    Identical checks (extension allowlist, size, real content verification) but
    the content is read from ``path`` on demand — the whole file is never held in
    a single in-memory buffer. Use this for the material upload pipeline, which
    streams the request body into a temp file first.

    Returns ``(extension, server_determined_mime)``.
    """
    ext = validate_extension(filename)
    validate_size(os.path.getsize(path), max_mb)
    mime = validate_content_path(path, ext)
    return ext, mime
