"""Unit tests: file upload validation (content verification, not MIME trust)."""
import io
import zipfile

import pytest
from PIL import Image

from app.services.file_validation import (
    EXTENSION_MIME,
    FileValidationError,
    normalize_extension,
    validate_content,
    validate_extension,
    validate_size,
    validate_upload,
)


# ---- fixtures: real (small) file bytes generated in-memory ----

def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _image_bytes(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format=fmt)
    return buf.getvalue()


def _ooxml_bytes(kind: str, extra=None) -> bytes:
    """A minimal but structurally-valid DOCX/PPTX (ZIP + required parts).

    ``extra`` is an optional list of ``(name, data)`` pairs added as extra
    archive entries — used by the zip-bomb tests."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="..."><Default Extension="xml" ContentType="text/xml"/></Types>')
        if kind == "docx":
            zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="..."/>')
        else:
            zf.writestr("ppt/presentation.xml", '<?xml version="1.0"?><p:presentation xmlns:p="..."/>')
        for name, data in (extra or []):
            zf.writestr(name, data)
    return buf.getvalue()


def test_normalize_extension():
    assert normalize_extension("Notes.PDF") == "pdf"
    assert normalize_extension("image.jpeg") == "jpeg"
    assert normalize_extension("noext") == ""


def test_validate_extension_allowed():
    assert validate_extension("doc.pdf") == "pdf"


def test_validate_extension_rejected():
    with pytest.raises(FileValidationError):
        validate_extension("malware.exe")


def test_validate_size_too_large(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    with pytest.raises(FileValidationError):
        validate_size(2 * 1024 * 1024, max_mb=1)


def test_validate_size_empty():
    with pytest.raises(FileValidationError):
        validate_size(0)


# ---- content verification: valid files ----

def test_validate_content_pdf_ok():
    assert validate_content(_pdf_bytes(), "pdf") == "application/pdf"


def test_validate_content_pdf_with_leading_bytes_ok():
    """Real-world PDFs (scanners, email wrappers, editors) often carry a few
    leading bytes before %PDF-. The spec allows the header within the first
    1024 bytes, so these are valid PDFs and must be accepted."""
    assert validate_content(b"LEADING-GARBAGE!!!" + _pdf_bytes(), "pdf") == "application/pdf"


def test_validate_content_pdf_with_trailing_bytes_ok():
    """Trailing bytes after %%EOF (signatures, appended metadata) are tolerated
    by the spec and by pypdf in lenient mode."""
    assert validate_content(_pdf_bytes() + b"\x00" * 256, "pdf") == "application/pdf"


@pytest.mark.parametrize("ext,fmt", [("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG"), ("webp", "WEBP")])
def test_validate_content_image_ok(ext, fmt):
    assert validate_content(_image_bytes(fmt), ext) == EXTENSION_MIME[ext]


def test_validate_content_docx_ok():
    assert validate_content(_ooxml_bytes("docx"), "docx").startswith("application/vnd.openxmlformats")


def test_validate_content_pptx_ok():
    assert validate_content(_ooxml_bytes("pptx"), "pptx").startswith("application/vnd.openxmlformats")


# ---- content verification: rejections ----

def test_validate_content_pdf_renamed_to_jpg_rejected():
    # Real PDF bytes presented with a .jpg extension → Pillow cannot decode.
    with pytest.raises(FileValidationError):
        validate_content(_pdf_bytes(), "jpg")


def test_validate_content_executable_renamed_to_pdf_rejected():
    # No %PDF- header → rejected before the parser is even invoked.
    with pytest.raises(FileValidationError):
        validate_content(b"MZ\x90\x00" + b"\x00" * 512, "pdf")


def test_validate_content_corrupt_pdf_rejected():
    pdf = bytearray(_pdf_bytes())
    # Truncate the tail (xref + %%EOF) so strict parsing fails.
    del pdf[-200:]
    with pytest.raises(FileValidationError):
        validate_content(bytes(pdf), "pdf")


def test_validate_content_corrupt_docx_rejected():
    docx = bytearray(_ooxml_bytes("docx"))
    # Flip bytes in the middle of the ZIP to corrupt it.
    mid = len(docx) // 2
    docx[mid:mid + 8] = b"\xff\xff\xff\xff\xff\xff\xff\xff"
    with pytest.raises(FileValidationError):
        validate_content(bytes(docx), "docx")


def test_validate_content_png_with_jpeg_extension_rejected():
    # PNG content declared as .jpg → format/ext mismatch.
    with pytest.raises(FileValidationError):
        validate_content(_image_bytes("PNG"), "jpg")


def test_validate_content_empty_rejected():
    with pytest.raises(FileValidationError):
        validate_content(b"", "pdf")


# ---- validate_upload end-to-end (pure) ----

def test_validate_upload_happy_path_returns_ext_and_server_mime():
    data = _pdf_bytes()
    ext, mime = validate_upload("notes.pdf", data)
    assert ext == "pdf"
    assert mime == "application/pdf"


def test_validate_upload_rejects_extension():
    with pytest.raises(FileValidationError):
        validate_upload("bad.exe", b"whatever")


# ---- zip-bomb protection (DOCX/PPTX) ----

def _patch_cd_uncompressed_size(zip_bytes: bytes, entry_name: str, new_size: int) -> bytes:
    """Overwrite the central-directory 'uncompressed size' field for one entry.

    Crafts a *lying* archive — whose central directory declares a tiny
    uncompressed size for an entry whose deflate stream actually decompresses
    larger — so the bounded-CRC check (actual decompression size) can be
    exercised, not just the declared-size guards.
    """
    data = bytearray(zip_bytes)
    sig = b"PK\x01\x02"  # central directory file header signature
    pos = 0
    while True:
        idx = data.find(sig, pos)
        if idx < 0:
            break
        fname_len = int.from_bytes(data[idx + 28:idx + 30], "little")
        extra_len = int.from_bytes(data[idx + 30:idx + 32], "little")
        comment_len = int.from_bytes(data[idx + 32:idx + 34], "little")
        fname_start = idx + 46
        fname = bytes(data[fname_start:fname_start + fname_len]).decode("utf-8", "replace")
        if fname == entry_name:
            # Uncompressed size is the 4-byte field at offset 24 in the CD entry.
            data[idx + 24:idx + 28] = new_size.to_bytes(4, "little")
        pos = idx + 46 + fname_len + extra_len + comment_len
    return bytes(data)


def test_docx_too_many_entries_rejected():
    """An archive with more than the allowed number of parts is rejected before
    any decompression (entry-count guard)."""
    from app.services import file_validation
    extra = [(f"junk/{i}.xml", b"<x/>") for i in range(file_validation._OOXML_MAX_ENTRIES + 1)]
    with pytest.raises(FileValidationError):
        validate_content(_ooxml_bytes("docx", extra), "docx")


def test_pptx_too_many_entries_rejected():
    from app.services import file_validation
    extra = [(f"junk/{i}.xml", b"<x/>") for i in range(file_validation._OOXML_MAX_ENTRIES + 1)]
    with pytest.raises(FileValidationError):
        validate_content(_ooxml_bytes("pptx", extra), "pptx")


def test_docx_extreme_compression_ratio_rejected():
    """A highly-compressible entry (1 MB of zeros -> ~1 KB compressed) yields an
    extreme compression ratio and is rejected by the ratio guard."""
    with pytest.raises(FileValidationError):
        validate_content(_ooxml_bytes("docx", [("big.bin", b"\x00" * 1_000_000)]), "docx")


def test_docx_oversized_single_entry_rejected(monkeypatch):
    """An entry whose declared uncompressed size exceeds the per-entry cap is
    rejected (per-entry size guard). The cap is lowered so the test need not
    build a 100 MB entry."""
    from app.services import file_validation
    monkeypatch.setattr(file_validation, "_OOXML_MAX_ENTRY_UNCOMPRESSED", 4096)
    with pytest.raises(FileValidationError):
        validate_content(_ooxml_bytes("docx", [("big.bin", b"\x00" * 10_000)]), "docx")


def test_docx_oversized_total_rejected(monkeypatch):
    """An archive whose total declared uncompressed size exceeds the total cap is
    rejected (total-size guard). Cap lowered for the test."""
    from app.services import file_validation
    monkeypatch.setattr(file_validation, "_OOXML_MAX_TOTAL_UNCOMPRESSED", 4096)
    with pytest.raises(FileValidationError):
        validate_content(_ooxml_bytes("docx", [("big.bin", b"\x00" * 10_000)]), "docx")


def test_docx_lying_decompression_bomb_rejected(monkeypatch):
    """An entry whose central directory declares a tiny uncompressed size but
    whose deflate stream actually decompresses large is rejected by the bounded
    CRC check on ACTUAL decompression size — the declared-size guards alone do
    not catch a lying archive (a real decompression bomb)."""
    from app.services import file_validation
    monkeypatch.setattr(file_validation, "_OOXML_MAX_ENTRY_UNCOMPRESSED", 4096)
    actual = b"\x00" * 50_000  # 50 KB actual; declared will be lied to 10 bytes
    raw = _ooxml_bytes("docx", [("big.bin", actual)])
    lied = _patch_cd_uncompressed_size(raw, "big.bin", 10)
    with pytest.raises(FileValidationError):
        validate_content(lied, "docx")


def test_valid_docx_with_extra_parts_accepted():
    """A normal DOCX carrying a few legitimate extra parts (docProps, embedded
    media) is accepted — the zip-bomb guards do not reject well-formed docs."""
    extra = [
        ("docProps/core.xml", b'<?xml version="1.0"?><cp:coreProperties xmlns:cp="..."/>'),
        ("word/media/logo.bin", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64),
    ]
    assert validate_content(_ooxml_bytes("docx", extra), "docx").startswith("application/vnd.openxmlformats")
