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


def _ooxml_bytes(kind: str) -> bytes:
    """A minimal but structurally-valid DOCX/PPTX (ZIP + required parts)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="..."><Default Extension="xml" ContentType="text/xml"/></Types>')
        if kind == "docx":
            zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="..."/>')
        else:
            zf.writestr("ppt/presentation.xml", '<?xml version="1.0"?><p:presentation xmlns:p="..."/>')
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
