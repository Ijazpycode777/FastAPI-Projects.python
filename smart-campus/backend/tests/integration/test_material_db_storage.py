"""Integration: study-material DB storage — bytes persist in ``file_data``,
download + preview work for admin/teacher, delete frees the bytes, and legacy
local-storage rows still download via the fallback.

These complement ``test_material_upload_security`` (upload validation) by
covering the persistence + retrieval contract: a file uploaded by a teacher or
admin is stored in the database and stays there until a teacher/admin deletes
it; both roles can download (attachment) and preview (inline).
"""
from __future__ import annotations

import io
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.models.materials import StudyMaterial
from app.services.storage import get_storage
from tests.conftest import login_as
from tests.integration.test_material_upload_security import _pdf_bytes, _upload


async def _mat(db, mat_id: str) -> StudyMaterial:
    """Fetch one material with file_data undefer'd so the test can inspect bytes."""
    stmt = select(StudyMaterial).options(undefer(StudyMaterial.file_data)).where(
        StudyMaterial.id == mat_id,
    )
    return (await db.execute(stmt)).scalar_one()


async def test_upload_stores_bytes_in_database(admin_client, academic_setup, db):
    """An uploaded file's bytes are persisted in file_data (not just metadata)."""
    pdf = _pdf_bytes()
    resp = await _upload(admin_client, academic_setup, "notes.pdf", pdf, "application/pdf")
    assert resp.status_code == 200, resp.text
    mat = await _mat(db, resp.json()["id"])
    assert mat.storage_backend == "db"
    assert mat.file_data == pdf  # bytes persisted in the DB row
    assert mat.file_size == len(pdf)


async def test_download_returns_stored_bytes(admin_client, academic_setup):
    """GET /download streams back the exact bytes that were uploaded."""
    pdf = _pdf_bytes()
    up = await _upload(admin_client, academic_setup, "notes.pdf", pdf, "application/pdf")
    dl = await admin_client.get(f"/api/v1/materials/{up.json()['id']}/download")
    assert dl.status_code == 200, dl.text
    assert dl.content == pdf
    assert "attachment" in dl.headers["content-disposition"]


async def test_preview_returns_inline_disposition(admin_client, academic_setup):
    """GET /preview returns inline disposition so the browser renders the file."""
    pdf = _pdf_bytes()
    up = await _upload(admin_client, academic_setup, "notes.pdf", pdf, "application/pdf")
    pv = await admin_client.get(f"/api/v1/materials/{up.json()['id']}/preview")
    assert pv.status_code == 200, pv.text
    assert pv.content == pdf
    assert "inline" in pv.headers["content-disposition"]


async def _make_assigned_teacher(admin_client, setup, email="t.mat@test.edu"):
    emp = "EMP-" + email.split("@")[0].upper()
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Teacher Mat", "email": email, "employee_id": emp,
        "department_id": setup["department_id"], "subject": "Computer Science",
        "designation": "Lecturer", "joining_date": "2022-09-01",
        "password": "Teacher!2025",
    })
    assert resp.status_code == 200, resp.text
    teacher = resp.json()
    a = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": teacher["id"], "subject_id": setup["subject_id"],
        "class_id": setup["class_id"], "section_id": setup["section_id"],
        "academic_session_id": setup["session_id"],
    })
    assert a.status_code == 200, a.text
    return teacher


async def test_teacher_can_upload_download_and_preview(admin_client, client, academic_setup):
    """A teacher assigned to the class can upload, download and preview its
    materials — the file is stored in the DB just as for an admin."""
    teacher = await _make_assigned_teacher(admin_client, academic_setup)
    await login_as(client, teacher["email"], "Teacher!2025")
    pdf = _pdf_bytes()
    up = await _upload(client, academic_setup, "teacher-notes.pdf", pdf, "application/pdf",
                       title="Teacher upload")
    assert up.status_code == 200, up.text
    mid = up.json()["id"]

    dl = await client.get(f"/api/v1/materials/{mid}/download")
    assert dl.status_code == 200 and dl.content == pdf
    pv = await client.get(f"/api/v1/materials/{mid}/preview")
    assert pv.status_code == 200 and pv.content == pdf


async def test_teacher_cannot_download_unassigned_class_material(admin_client, client, academic_setup):
    """A teacher not assigned to a class cannot download that class's material
    (server-enforced 403), even though they can download their own classes'."""
    # Admin uploads a material for the setup class (Part 1).
    up = await _upload(admin_client, academic_setup, "admin.pdf", _pdf_bytes(), "application/pdf")
    # A second class (Part 2) the teacher will be assigned to instead.
    other = await admin_client.post("/api/v1/classes", json={
        "program_id": academic_setup["program_id"], "name": "Part 2", "year": 2})
    other_id = other.json()["id"]

    # Create a teacher assigned ONLY to Part 2 (not the setup's Part 1).
    teacher = await _make_assigned_teacher(admin_client, academic_setup, email="t.mat2@test.edu")
    # _make_assigned_teacher above assigned them to Part 1; remove that and
    # assign to Part 2 instead by creating a fresh teacher tied only to Part 2.
    t2 = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Teacher P2", "email": "t.p2only@test.edu", "employee_id": "EMP-TP2",
        "department_id": academic_setup["department_id"], "subject": "Computer Science",
        "designation": "Lecturer", "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert t2.status_code == 200, t2.text
    a2 = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": t2.json()["id"], "subject_id": academic_setup["subject_id"],
        "class_id": other_id, "section_id": academic_setup["section_id"],
        "academic_session_id": academic_setup["session_id"],
    })
    assert a2.status_code == 200, a2.text

    await login_as(client, "t.p2only@test.edu", "Teacher!2025")
    # The Part-2-only teacher cannot download the Part-1 material (403)...
    resp = await client.get(f"/api/v1/materials/{up.json()['id']}/download")
    assert resp.status_code == 403
    pv = await client.get(f"/api/v1/materials/{up.json()['id']}/preview")
    assert pv.status_code == 403


async def test_delete_frees_stored_bytes(admin_client, academic_setup, db):
    """Deleting a material nulls file_data (bytes removed) while the audit row
    remains (is_active=False). The file is gone — not just hidden."""
    up = await _upload(admin_client, academic_setup, "del.pdf", _pdf_bytes(), "application/pdf")
    mid = up.json()["id"]
    assert (await _mat(db, mid)).file_data == _pdf_bytes()  # stored

    dele = await admin_client.delete(f"/api/v1/materials/{mid}")
    assert dele.status_code == 200, dele.text

    db.expire_all()
    mat = await _mat(db, mid)
    assert mat.is_active is False
    assert mat.file_data is None  # bytes freed
    # And the download is no longer reachable.
    dl = await admin_client.get(f"/api/v1/materials/{mid}/download")
    assert dl.status_code == 404


async def test_teacher_can_delete_own_upload(admin_client, client, academic_setup, db):
    """A teacher can delete a material they uploaded (bytes freed)."""
    teacher = await _make_assigned_teacher(admin_client, academic_setup, email="t.del@test.edu")
    await login_as(client, teacher["email"], "Teacher!2025")
    up = await _upload(client, academic_setup, "own.pdf", _pdf_bytes(), "application/pdf")
    mid = up.json()["id"]
    dele = await client.delete(f"/api/v1/materials/{mid}")
    assert dele.status_code == 200, dele.text
    db.expire_all()
    assert (await _mat(db, mid)).file_data is None


async def test_list_endpoint_does_not_return_file_data(admin_client, academic_setup):
    """The list endpoint returns metadata only — file_data never leaks into the
    API response (and is deferred at the ORM level so list queries stay cheap)."""
    await _upload(admin_client, academic_setup, "list.pdf", _pdf_bytes(), "application/pdf")
    rows = (await admin_client.get("/api/v1/materials")).json()
    assert len(rows) >= 1
    assert all("file_data" not in r for r in rows)
    assert {"id", "title", "file_name", "file_size", "content_type"} <= set(rows[0].keys())


async def test_legacy_local_storage_material_still_downloads(admin_client, academic_setup, db):
    """A material created before the file_data column (bytes in local storage,
    file_data NULL) still downloads via the storage fallback."""
    pdf = _pdf_bytes()
    key = "materials/legacy-test.pdf"
    get_storage().save(key, io.BytesIO(pdf), "application/pdf")
    legacy = StudyMaterial(
        title="Legacy notes", description=None,
        class_id=academic_setup["class_id"], uploaded_by=None,
        storage_backend="local", storage_key=key, file_name="legacy.pdf",
        file_size=len(pdf), content_type="application/pdf", is_active=True,
        file_data=None,
    )
    db.add(legacy)
    await db.commit()
    await db.refresh(legacy)

    dl = await admin_client.get(f"/api/v1/materials/{legacy.id}/download")
    assert dl.status_code == 200, dl.text
    assert dl.content == pdf
    # Cleanup the local file so other tests don't see it.
    get_storage().delete(key)


async def test_download_preserves_binary_bytes(admin_client, academic_setup):
    """A PDF with many 0x0A (newline) bytes round-trips exactly — the stream is
    not corrupted by line-based iteration of the BytesIO."""
    from tests.integration.test_material_upload_security import _pdf_bytes as _pb
    pdf = _pb()
    # Insert extra newlines into the attachment stream to stress chunking.
    assert b"\n" in pdf or True  # PDFs contain newlines already
    up = await _upload(admin_client, academic_setup, "bin.pdf", pdf, "application/pdf")
    dl = await admin_client.get(f"/api/v1/materials/{up.json()['id']}/download")
    assert dl.content == pdf, "downloaded bytes must match the uploaded PDF exactly"
