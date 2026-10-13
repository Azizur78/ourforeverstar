"""A verified customer may add a recovery email once; the admin can then find the registry by it."""
import json

from fastapi.testclient import TestClient

from app.main import create_app
from conftest import registry_payload


def verified(settings, number="DEV-2026-000001", code="TEST-CODE-1"):
    c = TestClient(create_app(settings))
    r = c.post("/api/registries/verify", json={"registry_number": number, "registry_code": code})
    return c, r.json()["public_id"]


def test_page_says_no_email_is_saved_and_the_customer_can_add_one(settings, admin, registry):
    c, pid = verified(settings)
    assert c.get(f"/api/registries/{pid}").json()["has_contact_email"] is False
    r = c.post(f"/api/registries/{pid}/contact-email", json={"email": "  Mira@Example.COM "})
    assert r.status_code == 200 and r.json() == {"saved": True}
    page = c.get(f"/api/registries/{pid}").json()
    assert page["has_contact_email"] is True and "mira@example.com" not in json.dumps(page)
    assert admin.get(f"/api/admin/registries/{registry['id']}").json()["contact_email"] == "mira@example.com"


def test_a_registry_with_an_email_already_saved_is_not_prompted_and_cannot_be_overwritten(settings, admin):
    admin.post("/api/admin/registries", json=registry_payload(contact_email="owner@example.com"))
    c, pid = verified(settings)
    assert c.get(f"/api/registries/{pid}").json()["has_contact_email"] is True
    r = c.post(f"/api/registries/{pid}/contact-email", json={"email": "other@example.com"})
    assert r.status_code == 409
    reg = admin.get("/api/admin/registries").json()["items"][0]
    assert reg["contact_email"] == "owner@example.com"


def test_only_a_verified_customer_of_that_registry_can_save_an_email(settings, admin, registry):
    _, pid = verified(settings)
    anonymous = TestClient(create_app(settings))
    assert anonymous.post(f"/api/registries/{pid}/contact-email", json={"email": "a@example.com"}).status_code == 401
    admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV-2026-000002", registry_code="TEST-CODE-2"))
    other, other_pid = verified(settings, "DEV-2026-000002", "TEST-CODE-2")
    assert other.post(f"/api/registries/{pid}/contact-email", json={"email": "a@example.com"}).status_code == 401
    assert admin.get(f"/api/admin/registries/{registry['id']}").json()["contact_email"] in (None, "")


def test_invalid_or_extra_input_is_rejected(settings, admin, registry):
    c, pid = verified(settings)
    for body in ({"email": "not-an-email"}, {"email": ""}, {"email": "a@example.com", "status": "inactive"}, {}):
        assert c.post(f"/api/registries/{pid}/contact-email", json=body).status_code == 422, body
    assert admin.get(f"/api/admin/registries/{registry['id']}").json()["contact_email"] in (None, "")


def test_saving_is_rate_limited(settings, admin, registry):
    c, pid = verified(settings)
    codes = [c.post(f"/api/registries/{pid}/contact-email", json={"email": "x@example.com"}).status_code for _ in range(12)]
    assert codes[0] == 200 and codes[1] == 409 and codes[-1] == 429


def test_admin_can_search_registries_by_the_saved_email(settings, admin, registry):
    c, pid = verified(settings)
    c.post(f"/api/registries/{pid}/contact-email", json={"email": "findme@example.com"})
    hit = admin.get("/api/admin/registries", params={"q": "findme@example"}).json()
    assert [r["registry_number"] for r in hit["items"]] == ["DEV-2026-000001"]
    assert admin.get("/api/admin/registries", params={"q": "nobody@example"}).json()["items"] == []
