"""Who may download the two customer PDFs, and what the customer-facing API reveals about them."""
import json
import sqlite3

from fastapi.testclient import TestClient

from app.main import create_app
from conftest import PDF, PDF2, PNG, registry_payload


def upload(admin, reg, kind, name, data):
    return admin.post(f"/api/admin/registries/{reg['id']}/{kind}", files={"file": (name, data)})


def verified(settings, number="DEV-2026-000001", code="TEST-CODE-1"):
    c = TestClient(create_app(settings))
    r = c.post("/api/registries/verify", json={"registry_number": number, "registry_code": code})
    return c, r.json()["public_id"]


def test_verified_customer_downloads_both_documents_as_pdf_attachments(settings, admin, registry):
    upload(admin, registry, "certificate", "c.pdf", PDF)
    upload(admin, registry, "registry-document", "r.pdf", PDF2)
    c, pid = verified(settings)
    cert = c.get(f"/api/registries/{pid}/certificate?download=1")
    doc = c.get(f"/api/registries/{pid}/registry-document?download=1")
    assert cert.status_code == doc.status_code == 200
    assert cert.content == PDF and doc.content == PDF2
    assert cert.headers["content-type"] == doc.headers["content-type"] == "application/pdf"
    assert cert.headers["content-disposition"] == 'attachment; filename="Star-Dedication-Certificate-DEV-2026-000001.pdf"'
    assert doc.headers["content-disposition"] == 'attachment; filename="Certificate-of-Celestial-Registry-DEV-2026-000001.pdf"'
    assert "no-store" in cert.headers["cache-control"] and cert.headers["x-content-type-options"] == "nosniff"
    assert c.get(f"/api/registries/{pid}/certificate").headers["content-disposition"].startswith("inline")


def test_the_page_says_which_documents_exist_without_revealing_anything_else(settings, admin, registry):
    upload(admin, registry, "certificate", "c.pdf", PDF)
    c, pid = verified(settings)
    page = c.get(f"/api/registries/{pid}").json()
    assert page["certificate"] == {"available": True, "content_type": "application/pdf", "label": "Star Dedication Certificate"}
    assert page["registry_document"] == {"available": False, "content_type": None, "label": "Certificate of Celestial Registry"}
    text = json.dumps(page)
    for forbidden in ("certificates/", ".pdf", "size", "uploaded_at", "certificate_path", "registry_document_path"):
        assert forbidden not in text, forbidden
    assert "contact_email" not in page and set(page) >= {"has_contact_email"}


def test_a_missing_document_is_a_clear_404_for_each_kind(settings, registry):
    c, pid = verified(settings)
    a = c.get(f"/api/registries/{pid}/certificate")
    b = c.get(f"/api/registries/{pid}/registry-document")
    assert (a.status_code, a.json()["message"]) == (404, "Star Dedication Certificate currently unavailable.")
    assert (b.status_code, b.json()["message"]) == (404, "Certificate of Celestial Registry currently unavailable.")


def test_no_document_without_verification_and_none_across_registries(settings, admin, registry):
    upload(admin, registry, "certificate", "c.pdf", PDF)
    other = admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV-2026-000002", registry_code="OTHER-CODE-2")).json()
    upload(admin, other, "certificate", "o.pdf", PDF2)
    anonymous = TestClient(create_app(settings))
    assert anonymous.get(f"/api/registries/{registry['public_id']}/certificate").status_code == 401
    c, _ = verified(settings, "DEV-2026-000002", "OTHER-CODE-2")
    assert c.get(f"/api/registries/{registry['public_id']}/certificate").status_code == 401         # not their registry
    assert c.get(f"/api/registries/{registry['public_id']}/registry-document").status_code == 401
    assert c.get(f"/api/registries/{other['public_id']}/certificate").content == PDF2


def test_deactivating_a_registry_stops_downloads(settings, admin, registry):
    upload(admin, registry, "certificate", "c.pdf", PDF)
    c, pid = verified(settings)
    assert c.get(f"/api/registries/{pid}/certificate").status_code == 200
    admin.delete(f"/api/admin/registries/{registry['id']}")
    assert c.get(f"/api/registries/{pid}/certificate").status_code == 404


def test_documents_uploaded_before_the_pdf_rule_stay_downloadable(settings, admin, registry):
    key = "certificates/" + "a" * 32 + ".png"
    (settings.upload_dir / "certificates").mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / key).write_bytes(PNG)
    with sqlite3.connect(settings.database_path) as conn:
        conn.execute("UPDATE registries SET certificate_path = ?", (key,))
    c, pid = verified(settings)
    r = c.get(f"/api/registries/{pid}/certificate?download=1")
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
    assert r.headers["content-disposition"].endswith('.png"')


def test_a_tampered_storage_key_is_never_followed(settings, admin, registry):
    secret = settings.upload_dir / "secret.txt"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("TOP-SECRET")
    for key in ("../secret.txt", "certificates/../secret.txt", "/etc/passwd", str(secret), "certificates/" + "z" * 32 + ".pdf"):
        with sqlite3.connect(settings.database_path) as conn:
            conn.execute("UPDATE registries SET certificate_path = ?", (key,))
        c, pid = verified(settings)
        r = c.get(f"/api/registries/{pid}/certificate")
        assert r.status_code == 404 and "TOP-SECRET" not in r.text, key


def test_a_file_missing_from_disk_is_a_404_not_a_server_error(settings, admin, registry):
    upload(admin, registry, "certificate", "c.pdf", PDF)
    for f in (settings.upload_dir / "certificates").glob("*.pdf"):
        f.unlink()
    c, pid = verified(settings)
    assert c.get(f"/api/registries/{pid}/certificate").status_code == 404


def test_download_filenames_are_always_filename_safe(settings, admin):
    reg = admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV/2026/7", registry_code="SLASH-CODE-7")).json()
    upload(admin, reg, "certificate", "c.pdf", PDF)
    c, pid = verified(settings, "DEV/2026/7", "SLASH-CODE-7")
    disposition = c.get(f"/api/registries/{pid}/certificate?download=1").headers["content-disposition"]
    assert disposition == 'attachment; filename="Star-Dedication-Certificate-DEV_2026_7.pdf"'


def test_document_requests_are_rate_limited(settings, registry):
    c, pid = verified(settings)
    statuses = [c.get(f"/api/registries/{pid}/certificate").status_code for _ in range(31)]
    assert statuses[:30] == [404] * 30 and statuses[30] == 429
    blocked = c.get(f"/api/registries/{pid}/registry-document")
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers                      # shared across both documents


def test_unverified_attempts_count_towards_the_limit_too(settings, registry):
    anonymous = TestClient(create_app(settings))
    codes = [anonymous.get(f"/api/registries/{registry['public_id']}/certificate").status_code for _ in range(31)]
    assert codes[:30] == [401] * 30 and codes[30] == 429
