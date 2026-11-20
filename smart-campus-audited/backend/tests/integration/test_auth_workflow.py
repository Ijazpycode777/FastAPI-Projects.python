"""Integration: authentication & authorization workflows."""
async def test_admin_login_success(admin_client):
    me = await admin_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "admin"


async def test_login_wrong_password(client, admin_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.edu", "password": "WrongPass!2025"
    })
    assert resp.status_code == 401


async def test_login_unknown_user(client):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@test.edu", "password": "Anypass!2025"
    })
    assert resp.status_code == 401


async def test_protected_endpoint_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_logout_invalidates_session(admin_client):
    resp = await admin_client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    me = await admin_client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_admin_dashboard_requires_admin_role(admin_client):
    resp = await admin_client.get("/api/v1/dashboard/admin")
    assert resp.status_code == 200
    assert "stats" in resp.json()
