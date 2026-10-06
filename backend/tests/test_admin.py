from fastapi.testclient import TestClient

from app.main import create_app
from conftest import ADMIN_PASSWORD, registry_payload


def test_admin_routes_blocked_without_login(client):
    for method, path in [
        ("get", "/api/admin/registries"), ("get", "/api/admin/stats"), ("get", "/api/admin/me"),
        ("post", "/api/admin/registries"), ("get", "/api/admin/registries/1"),
        ("put", "/api/admin/registries/1"), ("delete", "/api/admin/registries/1"),
        ("post", "/api/admin/registries/1/certificate"), ("get", "/api/admin/registries/1/certificate"),
    ]:
        assert getattr(client, method)(path).status_code == 401, (method, path)


def test_login_wrong_password_rejected(client):
    r = client.post("/api/admin/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401
    r = client.post("/api/admin/login", json={"username": "someone", "password": ADMIN_PASSWORD})
    assert r.status_code == 401


def test_login_is_rate_limited(client):
    for _ in range(5):
        client.post("/api/admin/login", json={"username": "admin", "password": "nope"})
    r = client.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 429


def test_valid_login_grants_access_and_logout_revokes(client):
    r = client.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert client.get("/api/admin/me").status_code == 200
    client.post("/api/admin/logout")
    assert client.get("/api/admin/me").status_code == 401


def test_forged_session_cookie_rejected(client):
    client.cookies.set("fs_admin_session", "admin|9999999999|forged", path="/api/admin")
    assert client.get("/api/admin/me").status_code == 401


def test_login_disabled_when_no_password_hash_configured(settings):
    from dataclasses import replace
    c = TestClient(create_app(replace(settings, admin_password_hash="")))
    assert c.post("/api/admin/login", json={"username": "admin", "password": ""}).status_code == 422
    assert c.post("/api/admin/login", json={"username": "admin", "password": "x"}).status_code == 401


def test_create_registry_and_code_is_not_stored_in_plaintext(admin, registry, settings):
    import sqlite3
    row = sqlite3.connect(settings.database_path).execute("SELECT registry_code, registry_code_hash FROM registries").fetchone()
    assert "TEST-CODE-1" not in row[0] and "TEST-CODE-1" not in row[1]
    assert registry["registry_code"] == "TEST-CODE-1"


def test_duplicate_registry_number_rejected(admin, registry):
    r = admin.post("/api/admin/registries", json=registry_payload(registry_code="OTHER-CODE"))
    assert r.status_code == 409
    assert r.json()["field"] == "registry_number"
    # case-insensitive duplicate
    r = admin.post("/api/admin/registries", json=registry_payload(registry_number="dev-2026-000001"))
    assert r.status_code == 409


def test_edit_cannot_collide_with_another_registry_number(admin, registry):
    other = admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV-2026-000002")).json()
    r = admin.put(f"/api/admin/registries/{other['id']}", json=registry_payload(registry_number="DEV-2026-000001"))
    assert r.status_code == 409
    ok = admin.put(f"/api/admin/registries/{other['id']}", json=registry_payload(
        registry_number="DEV-2026-000002", dedicated_to="Renamed"))
    assert ok.status_code == 200 and ok.json()["dedicated_to"] == "Renamed"


def test_invalid_data_rejected(admin):
    for bad in [
        registry_payload(dedicated_to=""),
        registry_payload(dedicated_by="   "),
        registry_payload(registry_number="x"),
        registry_payload(registry_number="HAS SPACE"),
        registry_payload(registry_code="ab"),
        registry_payload(dedication_date="not-a-date"),
        registry_payload(status="deleted"),
        registry_payload(dedication_message="x" * 2001),
        {**registry_payload(), "id": 5},
    ]:
        r = admin.post("/api/admin/registries", json=bad)
        assert r.status_code == 422, bad
        assert r.json()["errors"]
    missing = registry_payload()
    del missing["registry_code"]
    assert admin.post("/api/admin/registries", json=missing).status_code == 422


def test_optional_star_fields_may_be_blank(admin):
    r = admin.post("/api/admin/registries", json=registry_payload(star_catalogue="", constellation=None, distance=" "))
    assert r.status_code == 201
    assert r.json()["star_catalogue"] is None


def test_search_by_all_supported_fields(admin, registry):
    admin.post("/api/admin/registries", json=registry_payload(
        registry_number="DEV-2026-000002", registry_code="ZZZZ-9999", dedicated_to="Hiba", dedicated_by="Abdullah"))

    def names(q, **kw):
        r = admin.get("/api/admin/registries", params={"q": q, **kw}).json()
        return sorted(i["registry_number"] for i in r["items"])

    assert names("000002") == ["DEV-2026-000002"]
    assert names("hiba") == ["DEV-2026-000002"]
    assert names("abdul") == ["DEV-2026-000002"]
    assert names("zzzz-9999") == ["DEV-2026-000002"]       # by exact registry code
    assert names("TEST-CODE-1") == ["DEV-2026-000001"]
    assert names("Test Person") == ["DEV-2026-000001"]
    assert names("%") == []                                  # wildcard is escaped
    assert len(admin.get("/api/admin/registries").json()["items"]) == 2


def test_activate_deactivate_and_stats(admin, registry):
    assert admin.get("/api/admin/stats").json() == {"total": 1, "active": 1, "inactive": 0}
    admin.patch(f"/api/admin/registries/{registry['id']}/status", json={"status": "inactive"})
    assert admin.get("/api/admin/stats").json() == {"total": 1, "active": 0, "inactive": 1}
    assert admin.get("/api/admin/registries", params={"status": "inactive"}).json()["total"] == 1
    admin.patch(f"/api/admin/registries/{registry['id']}/status", json={"status": "active"})
    assert admin.get("/api/admin/registries/%d" % registry["id"]).json()["status"] == "active"


def test_unknown_registry_is_404(admin):
    assert admin.get("/api/admin/registries/9999").status_code == 404
    assert admin.put("/api/admin/registries/9999", json=registry_payload()).status_code == 404


def test_errors_do_not_leak_internals(admin):
    r = admin.get("/api/admin/registries/abc")
    assert r.status_code == 422
    assert "Traceback" not in r.text and "sqlite" not in r.text.lower()
