from fastapi.testclient import TestClient

from app.main import create_app
from conftest import PDF, registry_payload

GENERIC = "Registry details could not be verified."


def customer(settings):
    return TestClient(create_app(settings))  # no admin cookie


def verify(c, number="DEV-2026-000001", code="TEST-CODE-1"):
    return c.post("/api/registries/verify", json={"registry_number": number, "registry_code": code})


def test_valid_credentials_succeed_and_unlock_registry(settings, registry):
    c = customer(settings)
    r = verify(c)
    assert r.status_code == 200
    public_id = r.json()["public_id"]
    assert "id" not in r.json()

    data = c.get(f"/api/registries/{public_id}").json()
    assert data["dedicated_to"] == "Test Person"
    assert data["registry_code"] == "TEST-CODE-1"
    assert data["star"]["constellation"] == "Testudo"
    assert "id" not in data and "status" not in data


def test_verification_is_case_and_whitespace_tolerant(settings, registry):
    assert verify(customer(settings), " dev-2026-000001 ", " test-code-1 ").status_code == 200


def test_wrong_number_fails_generically(settings, registry):
    r = verify(customer(settings), number="DEV-2026-999999")
    assert r.status_code == 404
    assert r.json()["message"] == GENERIC


def test_wrong_code_gives_same_response_as_wrong_number(settings, registry):
    c = customer(settings)
    wrong_code = verify(c, code="WRONG-CODE")
    wrong_number = verify(c, number="DEV-2026-999999", code="WRONG-CODE")
    assert wrong_code.status_code == wrong_number.status_code == 404
    assert wrong_code.json() == wrong_number.json() == {"message": GENERIC}


def test_inactive_registry_is_not_accessible(settings, admin, registry):
    admin.patch(f"/api/admin/registries/{registry['id']}/status", json={"status": "inactive"})
    c = customer(settings)
    r = verify(c)
    assert r.status_code == 404 and r.json()["message"] == GENERIC


def test_deactivating_after_verification_blocks_access(settings, admin, registry):
    c = customer(settings)
    public_id = verify(c).json()["public_id"]
    admin.delete(f"/api/admin/registries/{registry['id']}")
    assert c.get(f"/api/registries/{public_id}").status_code == 404


def test_registry_requires_verification_cookie(settings, registry):
    assert customer(settings).get(f"/api/registries/{registry['public_id']}").status_code == 401


def test_cookie_for_one_registry_does_not_unlock_another(settings, admin, registry):
    other = admin.post("/api/admin/registries", json=registry_payload(
        registry_number="DEV-2026-000002", registry_code="OTHER-CODE-2")).json()
    c = customer(settings)
    verify(c)
    assert c.get(f"/api/registries/{other['public_id']}").status_code == 401


def test_brute_force_is_rate_limited(settings, registry):
    c = customer(settings)
    for _ in range(10):
        assert verify(c, code="WRONG-CODE").status_code == 404
    blocked = verify(c, code="WRONG-CODE")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert verify(c).status_code == 429  # even the right code is held back


def test_certificate_is_served_only_to_verified_customer(settings, admin, registry):
    admin.post(f"/api/admin/registries/{registry['id']}/certificate", files={"file": ("c.pdf", PDF, "application/pdf")})
    c = customer(settings)
    assert c.get(f"/api/registries/{registry['public_id']}/certificate").status_code == 401
    public_id = verify(c).json()["public_id"]
    r = c.get(f"/api/registries/{public_id}/certificate")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert c.get(f"/api/registries/{public_id}/certificate?download=1").headers["content-disposition"].startswith("attachment")


def test_missing_certificate_is_a_clean_404(settings, registry):
    c = customer(settings)
    public_id = verify(c).json()["public_id"]
    assert c.get(f"/api/registries/{public_id}").json()["certificate"]["available"] is False
    assert c.get(f"/api/registries/{public_id}/certificate").status_code == 404
