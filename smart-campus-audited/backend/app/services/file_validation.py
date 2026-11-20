"""File upload validation (pure logic) for study materials."""
from __future__ import annotations

import os

from app.core.config import settings


class FileValidationError(Exception):
    pass


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


# Map allowed extensions to expected content-type prefixes for real sniffing.
EXTENSION_CONTENT_TYPE_MAP = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def validate_content_type(filename: str, detected_content_type: str) -> None:
    """Cross-check the sniffed content type against the declared extension."""
    ext = normalize_extension(filename)
    expected = EXTENSION_CONTENT_TYPE_MAP.get(ext)
    if expected is None:
        return  # unknown but extension already validated
    if detected_content_type.lower() != expected.lower():
        # Some sniffers report 'application/zip' for docx/pptx (they are zip).
        if ext in ("docx", "pptx") and detected_content_type.lower() in (
            "application/zip",
            "application/octet-stream",
        ):
            return
        raise FileValidationError(
            f"Content-Type '{detected_content_type}' does not match extension '.{ext}'."
        )


def validate_upload(filename: str, size_bytes: int, detected_content_type: str) -> str:
    """Run all checks; return the validated extension."""
    ext = validate_extension(filename)
    validate_size(size_bytes)
    validate_content_type(filename, detected_content_type)
    return ext
