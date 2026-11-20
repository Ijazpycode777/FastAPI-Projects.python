"""Unit tests: file upload validation."""
import pytest

from app.services.file_validation import (
    FileValidationError,
    normalize_extension,
    validate_content_type,
    validate_extension,
    validate_size,
    validate_upload,
)


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


def test_validate_content_type_match():
    validate_content_type("doc.pdf", "application/pdf")  # ok


def test_validate_content_type_mismatch():
    with pytest.raises(FileValidationError):
        validate_content_type("doc.pdf", "image/jpeg")


def test_validate_content_type_zip_for_docx_accepted():
    validate_content_type("doc.docx", "application/zip")  # zip allowed for docx


def test_validate_upload_happy_path():
    assert validate_upload("notes.pdf", 1024, "application/pdf") == "pdf"


def test_validate_upload_rejects_extension():
    with pytest.raises(FileValidationError):
        validate_upload("bad.exe", 1024, "application/octet-stream")
