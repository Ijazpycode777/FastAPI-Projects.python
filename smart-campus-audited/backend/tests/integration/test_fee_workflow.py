"""Integration: fee structures, invoices, payments, outstanding balance."""
from datetime import date


async def _student(admin_client, setup, email):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Stu Fee", "email": email, "admission_date": "2025-08-01",
        "program_id": setup["program_id"], "class_id": setup["class_id"],
        "section_id": setup["section_id"], "academic_session_id": setup["session_id"],
        "password": "Student!2025",
    })
    return resp.json()


async def test_invoice_payment_outstanding(admin_client, academic_setup):
    s1 = await _student(admin_client, academic_setup, "student.fee1@test.edu")
    struct = await admin_client.post("/api/v1/fees/structures", json={
        "name": "Tuition", "program_id": academic_setup["program_id"],
        "class_id": academic_setup["class_id"],
        "academic_session_id": academic_setup["session_id"],
        "amount": 50000, "frequency": "one_time", "due_after_days": 30,
    })
    assert struct.status_code == 200, struct.text
    inv = await admin_client.post("/api/v1/fees/invoices", json={
        "student_id": s1["id"], "fee_structure_id": struct.json()["id"],
        "issued_date": "2025-08-01",
    })
    assert inv.status_code == 200
    inv_id = inv.json()["id"]
    # Initially outstanding == amount.
    detail = await admin_client.get(f"/api/v1/fees/invoices/{inv_id}")
    assert detail.status_code == 200
    assert detail.json()["outstanding"] == 50000.0
    # Record a partial payment.
    pay = await admin_client.post("/api/v1/fees/payments", json={
        "invoice_id": inv_id, "amount": 20000, "paid_at": "2025-08-05",
        "method": "bank_transfer", "reference": "BNK-1",
    })
    assert pay.status_code == 200, pay.text
    detail2 = await admin_client.get(f"/api/v1/fees/invoices/{inv_id}")
    assert detail2.json()["outstanding"] == 30000.0
    assert detail2.json()["paid_amount"] == 20000.0
    assert detail2.json()["status"] == "partial"


async def test_payment_exceeding_balance_rejected(admin_client, academic_setup):
    s1 = await _student(admin_client, academic_setup, "student.fee2@test.edu")
    struct = await admin_client.post("/api/v1/fees/structures", json={
        "name": "Lab", "academic_session_id": academic_setup["session_id"],
        "amount": 1000, "frequency": "one_time",
    })
    inv = await admin_client.post("/api/v1/fees/invoices", json={
        "student_id": s1["id"], "fee_structure_id": struct.json()["id"],
        "issued_date": "2025-08-01",
    })
    inv_id = inv.json()["id"]
    over = await admin_client.post("/api/v1/fees/payments", json={
        "invoice_id": inv_id, "amount": 1500, "paid_at": "2025-08-05", "method": "cash",
    })
    assert over.status_code in (400, 422)


async def test_student_views_own_statement(admin_client, client, academic_setup):
    from tests.conftest import login_as
    s1 = await _student(admin_client, academic_setup, "student.fee3@test.edu")
    struct = await admin_client.post("/api/v1/fees/structures", json={
        "name": "Annual", "academic_session_id": academic_setup["session_id"],
        "amount": 20000, "frequency": "one_time",
    })
    await admin_client.post("/api/v1/fees/invoices", json={
        "student_id": s1["id"], "fee_structure_id": struct.json()["id"],
        "issued_date": "2025-08-01",
    })
    await login_as(client, "student.fee3@test.edu", "Student!2025")
    stmt = await client.get("/api/v1/fees/statement/me")
    assert stmt.status_code == 200
    assert stmt.json()["total_outstanding"] == 20000.0
