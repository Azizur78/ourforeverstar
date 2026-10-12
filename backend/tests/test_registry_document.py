import base64
import json
import sqlite3
from dataclasses import replace

from fastapi.testclient import TestClient

from app.database.connection import init_db
from app.main import create_app
from conftest import ADMIN_PASSWORD, PDF, PDF2, PNG, registry_payload
from test_batch import cert_files, count, post, rec


def upload_doc(admin, registry, name, data):
    return admin.post(f"/api/admin/registries/{registry['id']}/registry-document", files={"file": (name, data)})


def upload_cert(admin, registry, name, data):
    return admin.post(f"/api/admin/registries/{registry['id']}/certificate", files={"file": (name, data)})


def verify(c, number="DEV-2026-000001", code="TEST-CODE-1"):
    return c.post("/api/registries/verify", json={"registry_number": number, "registry_code": code})


# ---------------------------------------------------------------- admin upload

def test_new_records_start_without_a_registry_document(registry):
    assert registry["registry_document"]["available"] is False and registry["registry_document"]["content_type"] is None


def test_admin_can_upload_and_view_the_registry_document(admin, registry):
    r = upload_doc(admin, registry, "registry.pdf", PDF)
    assert r.status_code == 200
    assert r.json()["registry_document"]["available"] is True and r.json()["registry_document"]["content_type"] == "application/pdf"
    view = admin.get(f"/api/admin/registries/{registry['id']}/registry-document")
    assert view.status_code == 200 and view.content == PDF and view.headers["content-disposition"].startswith("inline")
    dl = admin.get(f"/api/admin/registries/{registry['id']}/registry-document?download=1")
    assert dl.headers["content-disposition"].startswith("attachment")
    assert "Certificate-of-Celestial-Registry-DEV-2026-000001.pdf" in dl.headers["content-disposition"]
    assert "private" in view.headers["cache-control"] and view.headers["x-content-type-options"] == "nosniff"


def test_registry_document_and_certificate_are_independent(admin, registry, settings):
    upload_cert(admin, registry, "cert.pdf", PDF2)
    r = upload_doc(admin, registry, "registry.pdf", PDF)
    assert r.json()["certificate"]["content_type"] == "application/pdf"
    assert r.json()["registry_document"]["content_type"] == "application/pdf"
    assert admin.get(f"/api/admin/registries/{registry['id']}/certificate").content == PDF2
    assert admin.get(f"/api/admin/registries/{registry['id']}/registry-document").content == PDF
    assert len(cert_files(settings)) == 2
    row = sqlite3.connect(settings.database_path).execute("SELECT certificate_path, registry_document_path FROM registries").fetchone()
    assert row[0] != row[1] and row[1].startswith("certificates/") and row[1].endswith(".pdf")      # only a path is stored, never bytes


def test_replacing_the_document_removes_the_old_file_and_leaves_the_certificate(admin, registry, settings):
    upload_cert(admin, registry, "cert.pdf", PDF2)
    upload_doc(admin, registry, "a.pdf", PDF)
    upload_doc(admin, registry, "b.pdf", PDF2)
    assert admin.get(f"/api/admin/registries/{registry['id']}/registry-document").content == PDF2
    assert len(cert_files(settings)) == 2                                # old document deleted, certificate kept


def test_unsupported_oversized_disguised_and_empty_documents_are_rejected(admin, registry, settings):
    assert upload_doc(admin, registry, "x.exe", b"MZ" + b"\0" * 30).status_code == 415
    assert upload_doc(admin, registry, "x.html", b"<html>").status_code == 415
    assert upload_doc(admin, registry, "evil.pdf", b"<script>alert(1)</script>").status_code == 415
    assert upload_doc(admin, registry, "empty.pdf", b"").status_code == 415
    big = upload_doc(admin, registry, "big.pdf", b"%PDF-" + b"0" * (1024 * 1024 + 10))
    assert big.status_code == 413 and "too large" in big.json()["message"].lower()
    assert cert_files(settings) == []
    assert admin.get(f"/api/admin/registries/{registry['id']}").json()["registry_document"]["available"] is False


def test_missing_document_is_a_clean_404_and_admin_routes_are_protected(admin, registry, client):
    r = admin.get(f"/api/admin/registries/{registry['id']}/registry-document")
    assert r.status_code == 404 and r.json()["message"] == "Certificate of Celestial Registry currently unavailable."
    assert upload_doc(admin, {"id": 9999}, "a.pdf", PDF).status_code == 404
    admin.post("/api/admin/logout")
    assert upload_doc(admin, registry, "a.pdf", PDF).status_code == 401
    assert admin.get(f"/api/admin/registries/{registry['id']}/registry-document").status_code == 401


# ---------------------------------------------------------------- customer access

def test_customer_sees_and_downloads_the_document_only_after_verifying(settings, admin, registry):
    upload_doc(admin, registry, "registry.pdf", PDF)
    customer = TestClient(create_app(settings))
    assert customer.get(f"/api/registries/{registry['public_id']}/registry-document").status_code == 401
    public_id = verify(customer).json()["public_id"]
    page = customer.get(f"/api/registries/{public_id}").json()
    assert page["registry_document"] == {"available": True, "content_type": "application/pdf", "label": "Certificate of Celestial Registry"}
    assert "registry_document_path" not in json.dumps(page) and "certificates/" not in json.dumps(page)
    doc = customer.get(f"/api/registries/{public_id}/registry-document")
    assert doc.status_code == 200 and doc.content == PDF
    assert customer.get(f"/api/registries/{public_id}/registry-document?download=1").headers["content-disposition"].startswith("attachment")


def test_document_follows_the_same_access_rules_as_the_registry(settings, admin, registry):
    upload_doc(admin, registry, "registry.pdf", PDF)
    other = admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV-2026-000002", registry_code="OTHER-CODE-2")).json()
    customer = TestClient(create_app(settings))
    verify(customer)
    assert customer.get(f"/api/registries/{other['public_id']}/registry-document").status_code == 401   # another registry's cookie
    admin.delete(f"/api/admin/registries/{registry['id']}")                                              # deactivate
    assert customer.get(f"/api/registries/{registry['public_id']}/registry-document").status_code == 404


def test_customer_without_a_document_gets_a_clean_404(settings, registry):
    customer = TestClient(create_app(settings))
    public_id = verify(customer).json()["public_id"]
    assert customer.get(f"/api/registries/{public_id}").json()["registry_document"]["available"] is False
    r = customer.get(f"/api/registries/{public_id}/registry-document")
    assert r.status_code == 404 and r.json()["message"] == "Certificate of Celestial Registry currently unavailable."


# ---------------------------------------------------------------- batch

def post_with_docs(client, records, certs=None, docs=None):
    certs, docs = certs or {}, docs or {}
    files = [("certificates", (n, d)) for _, (n, d) in certs.items()] + [("registry_documents", (n, d)) for _, (n, d) in docs.items()]
    return client.post("/api/admin/registries/batch", files=files or None, data={
        "records": json.dumps(records), "certificate_indexes": json.dumps(list(certs)),
        "registry_document_indexes": json.dumps(list(docs))})


def test_batch_attaches_each_document_to_its_own_record(admin, settings):
    r = post_with_docs(admin, [rec(1), rec(2), rec(3)], certs={2: ("c3.pdf", PDF2)}, docs={0: ("r1.pdf", PDF), 2: ("r3.pdf", PDF2)})
    assert r.status_code == 201
    one, two, three = sorted(r.json()["created"], key=lambda c: c["registry_number"])
    assert one["registry_document"]["content_type"] == "application/pdf" and not one["certificate"]["available"]
    assert not two["registry_document"]["available"] and not two["certificate"]["available"]     # nothing inherited
    assert three["registry_document"]["content_type"] == "application/pdf" and three["certificate"]["content_type"] == "application/pdf"
    assert admin.get(f"/api/admin/registries/{one['id']}/registry-document").content == PDF
    assert admin.get(f"/api/admin/registries/{two['id']}/registry-document").status_code == 404
    assert len(cert_files(settings)) == 3                                  # r1, c3 and r3: three distinct files


def test_one_bad_document_rejects_the_whole_batch_and_leaves_nothing_behind(admin, settings):
    r = post_with_docs(admin, [rec(1), rec(2)], certs={0: ("ok.pdf", PDF)}, docs={1: ("bad.exe", b"MZ" + b"\0" * 20)})
    assert r.status_code == 422
    assert {"index": 1, "field": "registry_document"}.items() <= r.json()["errors"][0].items()
    assert count(settings) == 0 and cert_files(settings) == []


def test_document_problems_are_reported_alongside_other_record_errors(admin, settings):
    r = post_with_docs(admin, [rec(1, dedicated_by=""), rec(2)], certs={1: ("bad.txt", b"hi")}, docs={0: ("bad.txt", b"hi")})
    assert sorted((e["index"], e["field"]) for e in r.json()["errors"]) == [(0, "dedicated_by"), (0, "registry_document"), (1, "certificate")]
    assert cert_files(settings) == [] and count(settings) == 0


def test_document_index_mismatches_are_rejected(admin, settings):
    for indexes in ([5], [0, 0], ["a"], []):
        r = admin.post("/api/admin/registries/batch", files=[("registry_documents", ("r.pdf", PDF))],
                       data={"records": json.dumps([rec(1)]), "registry_document_indexes": json.dumps(indexes)})
        assert r.status_code == 422, indexes
    assert count(settings) == 0 and cert_files(settings) == []


def test_database_failure_removes_documents_too(admin, settings, monkeypatch):
    from app.database import registry_repository as rr
    monkeypatch.setattr(rr.RegistryRepository, "create_many", lambda self, rows: (_ for _ in ()).throw(RuntimeError("disk full")))
    c = TestClient(create_app(settings), raise_server_exceptions=False)
    c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    r = post_with_docs(c, [rec(1)], certs={0: ("c.pdf", PDF2)}, docs={0: ("r.pdf", PDF)})
    assert r.status_code == 500 and "disk full" not in r.text
    assert cert_files(settings) == [] and count(settings) == 0


# ---------------------------------------------------------------- upgrading an existing database

OLD_SCHEMA = """
CREATE TABLE registries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE,
    registry_number TEXT NOT NULL UNIQUE COLLATE NOCASE, registry_code TEXT NOT NULL, registry_code_hash TEXT NOT NULL,
    dedicated_to TEXT NOT NULL, dedicated_by TEXT NOT NULL, dedication_date TEXT NOT NULL, occasion TEXT,
    star_catalogue TEXT, constellation TEXT, distance TEXT, dedication_message TEXT, certificate_path TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
"""


def test_existing_database_is_upgraded_in_place_without_losing_data(settings):
    db = settings.database_path
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(OLD_SCHEMA)
    conn.execute("INSERT INTO registries (public_id, registry_number, registry_code, registry_code_hash, dedicated_to, dedicated_by,"
                 " dedication_date, certificate_path, status, created_at, updated_at) VALUES ('pid','OLD-0001','enc','hash','To','By',"
                 "'2026-01-01','certificates/keep.png','inactive','t','t')")
    conn.commit(); conn.close()

    init_db(db); init_db(db)                                              # idempotent
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    assert "registry_document_path" in [r["name"] for r in conn.execute("PRAGMA table_info(registries)")]
    row = conn.execute("SELECT * FROM registries").fetchone()
    assert row["registry_number"] == "OLD-0001" and row["certificate_path"] == "certificates/keep.png"
    assert row["status"] == "inactive" and row["registry_document_path"] is None
    conn.close()

    c = TestClient(create_app(settings))                                   # the app runs on the upgraded database
    c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert c.get("/api/admin/stats").json() == {"total": 1, "active": 0, "inactive": 1}


# ---------------------------------------------------------------- staging seed

def test_staging_seed_restores_registry_documents_too(settings):
    seed = {"records": [{**registry_payload(), "registry_document": {"filename": "r.pdf", "content_base64": base64.b64encode(PDF).decode()},
                         "certificate": {"filename": "c.png", "content_base64": base64.b64encode(PNG).decode()}}]}  # legacy image
    c = TestClient(create_app(replace(settings, staging_seed_b64=base64.b64encode(json.dumps(seed).encode()).decode())))
    c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    item = c.get("/api/admin/registries").json()["items"][0]
    assert item["registry_document"]["content_type"] == "application/pdf" and item["certificate"]["content_type"] == "image/png"
    assert c.get(f"/api/admin/registries/{item['id']}/registry-document").content == PDF
