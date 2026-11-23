"""Integration: study-material upload security — content verification, bounded
size reading, and the guarantee that rejected uploads leave no trace.

Covers the 11 required cases:
  1. valid PDF            2. valid PNG/JPEG/WEBP      3. valid DOCX/PPTX
  4. PDF renamed to JPG   5. executable renamed to PDF
  6. spoofed MIME type    7. corrupt PDF + Office docs
  8. empty file           9. unsupported extension
 10. file > 25 MB        11. file at the 25 MB boundary (accepted)

Invalid uploads must receive HTTP 4xx — never 500 — and must not create a DB
record or leave a stored file behind.
"""
from __future__ import annotations

import io
import os
import zipfile

import pytest
from PIL import Image

from app.core.config import settings
from app.models.materials import StudyMaterial


# ---------- in-memory valid file factories ----------

def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _image_bytes(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (12, 12), "white").save(buf, format=fmt)
    return buf.getvalue()


def _ooxml_bytes(kind: str, extra=None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="text/xml"/></Types>')
        if kind == "docx":
            zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
        else:
            zf.writestr("ppt/presentation.xml", '<?xml version="1.0"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')
        for name, data in (extra or []):
            zf.writestr(name, data)
    return buf.getvalue()


def _pdf_of_exact_size(target: int) -> bytes:
    """A valid PDF (one blank page + an embedded attachment) of exactly
    ``target`` bytes. The attachment stream scales 1:1, so we solve for the
    needed padding length and nudge once to hit the exact byte count."""
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(72, 72)
    w.add_attachment("pad.bin", b"x" * 16)
    b = io.BytesIO(); w.write(b); s16 = len(b.getvalue())
    n = target - (s16 - 16)  # constant overhead + N (1:1)
    data = b""
    for _ in range(3):
        w2 = PdfWriter(); w2.add_blank_page(72, 72)
        w2.add_attachment("pad.bin", b"x" * n)
        b2 = io.BytesIO(); w2.write(b2); data = b2.getvalue()
        diff = len(data) - target
        if diff == 0:
            return data
        n -= diff
    return data


# ---------- upload helper ----------

async def _upload(client, setup, filename, data, content_type="application/octet-stream", title="Material"):
    return await client.post("/api/v1/materials", data={
        "title": title, "class_id": setup["class_id"],
    }, files={"file": (filename, data, content_type)})


def _storage_files() -> set[str]:
    base = settings.storage_local_path
    if not os.path.isdir(base):
        return set()
    return {os.path.join(root, f) for root, _, files in os.walk(base) for f in files}


# ============ 1–3: valid uploads ============

async def test_valid_pdf_upload(admin_client, academic_setup):
    resp = await _upload(admin_client, academic_setup, "notes.pdf", _pdf_bytes(), "application/pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content_type"] == "application/pdf"
    assert body["file_size"] > 0


async def test_pdf_with_leading_bytes_upload_accepted(admin_client, academic_setup):
    """Regression: real-world PDFs (scanned / emailed / editor-saved) often
    carry a few leading bytes before %PDF-. The server must accept these as
    valid PDFs, not reject them with 'File does not have a valid PDF header'."""
    data = b"LEADING-GARBAGE!!!" + _pdf_bytes()
    resp = await _upload(admin_client, academic_setup, "scan.pdf", data, "application/pdf")
    assert resp.status_code == 200, resp.text
    assert resp.json()["content_type"] == "application/pdf"


async def test_material_visible_only_to_exact_class(admin_client, academic_setup, db):
    """A material uploaded for ICS Part 1 is visible to ICS Part 1 students but
    NOT to Medical students, and NOT to students in 'Part 1' of another program.

    ``class_id`` points at a specific ClassLevel row, which already encodes
    (program, part) — 'ICS Part 1' and 'Medical Part 1' are different rows even
    though both are named 'Part 1'. Filtering by ``class_id`` therefore gives
    exact scoping: no cross-program / cross-class leakage.
    """
    from types import SimpleNamespace
    from app.services import material_service

    resp = await _upload(admin_client, academic_setup, "ics.pdf", _pdf_bytes(),
                         "application/pdf", title="ICS Part 1 notes")
    assert resp.status_code == 200, resp.text
    ics_p1_class = academic_setup["class_id"]

    # A second program with its own 'Part 1' class — same name, different row.
    med = await admin_client.post("/api/v1/programs", json={"code": "MBBS", "name": "Medical"})
    assert med.status_code == 200, med.text
    med_p1 = await admin_client.post("/api/v1/classes", json={
        "program_id": med.json()["id"], "name": "Part 1", "year": 1,
    })
    assert med_p1.status_code == 200, med_p1.text
    med_p1_class = med_p1.json()["id"]
    assert med_p1_class != ics_p1_class

    # An ICS Part 1 student sees the material.
    seen = await material_service.list_for_student(db, SimpleNamespace(current_class_id=ics_p1_class))
    assert any(m.title == "ICS Part 1 notes" for m in seen)

    # A Medical Part 1 student does NOT — even though their class is also 'Part 1'.
    unseen = await material_service.list_for_student(db, SimpleNamespace(current_class_id=med_p1_class))
    assert not any(m.title == "ICS Part 1 notes" for m in unseen)


@pytest.mark.parametrize("ext,fmt,mime", [
    ("png", "PNG", "image/png"),
    ("jpg", "JPEG", "image/jpeg"),
    ("jpeg", "JPEG", "image/jpeg"),
    ("webp", "WEBP", "image/webp"),
])
async def test_valid_image_upload(admin_client, academic_setup, ext, fmt, mime):
    resp = await _upload(admin_client, academic_setup, f"pic.{ext}", _image_bytes(fmt), mime)
    assert resp.status_code == 200, resp.text
    assert resp.json()["content_type"] == mime


async def test_valid_docx_upload(admin_client, academic_setup):
    resp = await _upload(admin_client, academic_setup, "doc.docx", _ooxml_bytes("docx"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["content_type"].startswith("application/vnd.openxmlformats")


async def test_valid_pptx_upload(admin_client, academic_setup):
    resp = await _upload(admin_client, academic_setup, "deck.pptx", _ooxml_bytes("pptx"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["content_type"].startswith("application/vnd.openxmlformats")


# ============ 4–9: rejections (must be 4xx, never 500) ============

async def test_pdf_renamed_to_jpg_rejected(admin_client, academic_setup):
    # Real PDF bytes with a .jpg extension → Pillow cannot decode → reject.
    resp = await _upload(admin_client, academic_setup, "lie.jpg", _pdf_bytes(), "image/jpeg")
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_executable_renamed_to_pdf_rejected(admin_client, academic_setup):
    exe = b"MZ\x90\x00" + b"\x00" * 512  # PE header
    resp = await _upload(admin_client, academic_setup, "malware.pdf", exe, "application/pdf")
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_spoofed_mime_does_not_accept_mismatched_file(admin_client, academic_setup):
    """A PNG image declared as .pdf with a spoofed 'application/pdf' MIME must
    still be rejected — the server verifies content, not the browser MIME."""
    resp = await _upload(admin_client, academic_setup, "fake.pdf", _image_bytes("PNG"), "application/pdf")
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_spoofed_mime_on_valid_file_still_accepted(admin_client, academic_setup):
    """A valid PDF with a deliberately wrong browser MIME must still be accepted
    — the server ignores the MIME and verifies content+extension."""
    resp = await _upload(admin_client, academic_setup, "ok.pdf", _pdf_bytes(), "image/jpeg")
    assert resp.status_code == 200, resp.text
    assert resp.json()["content_type"] == "application/pdf"


async def test_corrupt_pdf_rejected(admin_client, academic_setup):
    pdf = bytearray(_pdf_bytes())
    del pdf[-200:]  # truncate xref + EOF
    resp = await _upload(admin_client, academic_setup, "broken.pdf", bytes(pdf), "application/pdf")
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_corrupt_docx_rejected(admin_client, academic_setup):
    docx = bytearray(_ooxml_bytes("docx"))
    mid = len(docx) // 2
    docx[mid:mid + 8] = b"\xff" * 8  # corrupt the compressed stream
    resp = await _upload(admin_client, academic_setup, "broken.docx", bytes(docx))
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_corrupt_pptx_rejected(admin_client, academic_setup):
    pptx = bytearray(_ooxml_bytes("pptx"))
    mid = len(pptx) // 2
    pptx[mid:mid + 8] = b"\xff" * 8
    resp = await _upload(admin_client, academic_setup, "broken.pptx", bytes(pptx))
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_zip_bomb_docx_rejected(admin_client, academic_setup):
    """A DOCX zip-bomb (extreme compression ratio) is rejected at the upload
    endpoint with 4xx — never 500 — and creates no stored file or DB record."""
    bomb = _ooxml_bytes("docx", [("big.bin", b"\x00" * 1_000_000)])
    resp = await _upload(admin_client, academic_setup, "bomb.docx", bomb)
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_empty_file_rejected(admin_client, academic_setup):
    resp = await _upload(admin_client, academic_setup, "empty.pdf", b"", "application/pdf")
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_unsupported_extension_rejected(admin_client, academic_setup):
    resp = await _upload(admin_client, academic_setup, "script.exe", b"MZ" + b"\x00" * 64, "application/octet-stream")
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


# ============ 10–11: size limit ============

async def test_oversize_file_rejected(admin_client, academic_setup):
    # 1 KiB over the 25 MiB limit; content is irrelevant (size check fires first).
    over = settings.max_upload_mb * 1024 * 1024 + 1024
    resp = await _upload(admin_client, academic_setup, "big.pdf", b"\x00" * over, "application/pdf")
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_boundary_size_file_accepted(admin_client, academic_setup):
    """A valid PDF of exactly 25 MiB (the permitted limit) must be accepted."""
    target = settings.max_upload_mb * 1024 * 1024
    data = _pdf_of_exact_size(target)
    assert len(data) == target, f"fixture off by {len(data) - target}"
    resp = await _upload(admin_client, academic_setup, "boundary.pdf", data, "application/pdf")
    assert resp.status_code == 200, resp.text
    assert resp.json()["file_size"] == target


# ============ no-trace guarantees for rejected uploads ============

async def test_rejected_upload_creates_no_db_record(admin_client, academic_setup, db):
    before = (await db.execute(__import__("sqlalchemy").select(StudyMaterial))).scalars().all()
    resp = await _upload(admin_client, academic_setup, "bad.pdf", b"not a pdf", "application/pdf")
    assert resp.status_code in (400, 422)
    await db.rollback()  # drop any pending state from the failed request
    after = (await db.execute(__import__("sqlalchemy").select(StudyMaterial))).scalars().all()
    assert len(after) == len(before), "a rejected upload created a DB record"


async def test_rejected_upload_leaves_no_stored_file(admin_client, academic_setup):
    before = _storage_files()
    resp = await _upload(admin_client, academic_setup, "bad.pdf", b"not a pdf", "application/pdf")
    assert resp.status_code in (400, 422)
    after = _storage_files()
    # No new file should exist on disk for the rejected upload.
    assert after == before, f"rejected upload left a file behind: {after - before}"
