"""Private S3 storage, tested against an in-memory S3 (moto). Nothing here touches AWS.

Note: moto does not enforce the expiry of pre-signed URLs, so these tests verify the lifetime each URL is ISSUED
with (X-Amz-Expires); real S3 enforces it server-side.
"""
import json
import sqlite3
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
import requests
from fastapi.testclient import TestClient
from moto import mock_aws

from app.main import create_app
from app.services.s3_storage import S3DocumentStorage
from conftest import ADMIN_PASSWORD, PDF, PDF2, registry_payload

BUCKET = "test-docs-bucket"


@pytest.fixture()
def s3_client(monkeypatch):
    for name, value in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_DEFAULT_REGION": "us-east-1"}.items():
        monkeypatch.setenv(name, value)
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture()
def storage(s3_client):
    return S3DocumentStorage(BUCKET, "us-east-1", prefix="prod", url_ttl_seconds=300)


@pytest.fixture()
def s3_settings(settings, s3_client):
    return replace(settings, storage_backend="s3", s3_bucket=BUCKET, s3_region="us-east-1", s3_prefix="prod")


def objects(s3_client):
    return [o["Key"] for o in s3_client.list_objects_v2(Bucket=BUCKET).get("Contents", [])]


# ------------------------------------------------------------------ the storage class

def test_upload_is_encrypted_typed_prefixed_and_not_public(storage, s3_client):
    key = storage.save(".pdf", PDF)
    assert key.startswith("certificates/") and key.endswith(".pdf")       # the database key never contains the prefix
    head = s3_client.head_object(Bucket=BUCKET, Key=f"prod/{key}")
    assert head["ServerSideEncryption"] == "AES256" and head["ContentType"] == "application/pdf"
    grants = s3_client.get_object_acl(Bucket=BUCKET, Key=f"prod/{key}")["Grants"]
    assert not any("AllUsers" in str(g["Grantee"]) or "AuthenticatedUsers" in str(g["Grantee"]) for g in grants)


def test_exists_and_delete(storage):
    key = storage.save(".pdf", PDF)
    assert storage.exists(key) is True
    storage.delete(key)
    assert storage.exists(key) is False
    assert storage.exists("certificates/00000000000000000000000000000000.pdf") is False


def test_keys_are_generated_by_the_server_and_unique(storage):
    assert len({storage.save(".pdf", PDF) for _ in range(5)}) == 5


@pytest.mark.parametrize("bad", ["../secret.pdf", "certificates/../x.pdf", "other/abc.pdf", "certificates/abc.pdf",
                                 "/etc/passwd", "certificates/" + "g" * 32 + ".pdf", "", "prod/certificates/" + "a" * 32 + ".pdf"])
def test_arbitrary_keys_are_refused(storage, bad):
    assert storage.exists(bad) is False
    storage.delete(bad)                                    # a no-op, never an error and never a deletion
    with pytest.raises(ValueError):
        storage.download(bad, "x.pdf", "application/pdf", attachment=True)


def test_presigned_url_is_short_lived_read_only_and_forces_a_pdf_download(storage):
    key = storage.save(".pdf", PDF)
    response = storage.download(key, "Star-Dedication-Certificate-OFS-1.pdf", "application/pdf", attachment=True)
    assert response.status_code == 302
    assert response.headers["cache-control"] == "no-store" and response.headers["referrer-policy"] == "no-referrer"
    url = response.headers["location"]
    query = parse_qs(urlparse(url).query)
    assert query["X-Amz-Expires"] == ["300"] and "X-Amz-Signature" in query
    assert query["response-content-type"] == ["application/pdf"]
    assert query["response-content-disposition"] == ['attachment; filename="Star-Dedication-Certificate-OFS-1.pdf"']
    fetched = requests.get(url)
    assert fetched.status_code == 200 and fetched.content == PDF
    # Real S3 binds the signature to the GET method (a PUT with this URL is refused). moto does not verify
    # signatures, so that cannot be asserted here; what we can assert is that the URL targets exactly one object.
    assert urlparse(url).path == f"/prod/{key}" and query["X-Amz-SignedHeaders"] == ["host"]


def test_url_lifetime_follows_the_configured_ttl(s3_client):
    short = S3DocumentStorage(BUCKET, "us-east-1", url_ttl_seconds=90)
    key = short.save(".pdf", PDF)
    assert parse_qs(urlparse(short.download(key, "a.pdf", "application/pdf", attachment=False).headers["location"]).query)["X-Amz-Expires"] == ["90"]


def test_inline_view_uses_an_inline_disposition(storage):
    key = storage.save(".pdf", PDF)
    url = storage.download(key, "a.pdf", "application/pdf", attachment=False).headers["location"]
    assert parse_qs(urlparse(url).query)["response-content-disposition"][0].startswith("inline")


# ------------------------------------------------------------------ the whole app on S3

def admin_client(s3_settings):
    c = TestClient(create_app(s3_settings))
    assert c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200
    return c


def customer(s3_settings, number="DEV-2026-000001", code="TEST-CODE-1"):
    c = TestClient(create_app(s3_settings))
    r = c.post("/api/registries/verify", json={"registry_number": number, "registry_code": code})
    return c, r.json().get("public_id")


def test_admin_upload_goes_to_s3_and_the_database_keeps_only_a_key(s3_settings, s3_client):
    admin = admin_client(s3_settings)
    created = admin.post("/api/admin/registries", json=registry_payload()).json()
    r = admin.post(f"/api/admin/registries/{created['id']}/certificate", files={"file": ("c.pdf", PDF)})
    assert r.status_code == 200 and r.json()["certificate"]["size"] == len(PDF) and r.json()["certificate"]["uploaded_at"]
    stored = objects(s3_client)
    assert len(stored) == 1 and stored[0].startswith("prod/certificates/")
    row = sqlite3.connect(s3_settings.database_path).execute("SELECT certificate_path, certificate_size FROM registries").fetchone()
    assert row[0] == stored[0].removeprefix("prod/") and row[1] == len(PDF)             # a key and a size, never bytes or a URL


def test_verified_customer_is_redirected_to_a_short_lived_url_and_gets_the_pdf(s3_settings, s3_client):
    admin = admin_client(s3_settings)
    reg = admin.post("/api/admin/registries", json=registry_payload()).json()
    admin.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c.pdf", PDF)})
    admin.post(f"/api/admin/registries/{reg['id']}/registry-document", files={"file": ("r.pdf", PDF2)})
    c, pid = customer(s3_settings)
    for path, expected, name in [("certificate", PDF, "Star-Dedication-Certificate-DEV-2026-000001.pdf"),
                                 ("registry-document", PDF2, "Certificate-of-Celestial-Registry-DEV-2026-000001.pdf")]:
        r = c.get(f"/api/registries/{pid}/{path}?download=1", follow_redirects=False)
        assert r.status_code == 302 and r.headers["cache-control"] == "no-store"
        query = parse_qs(urlparse(r.headers["location"]).query)
        assert query["X-Amz-Expires"] == ["300"]
        assert query["response-content-disposition"] == [f'attachment; filename="{name}"']
        got = requests.get(r.headers["location"])
        assert got.status_code == 200 and got.content == expected and got.headers["content-type"] == "application/pdf"


def test_no_url_is_issued_without_verification_or_for_another_registry(s3_settings, s3_client):
    admin = admin_client(s3_settings)
    one = admin.post("/api/admin/registries", json=registry_payload()).json()
    two = admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV-2026-000002", registry_code="OTHER-CODE-2")).json()
    admin.post(f"/api/admin/registries/{one['id']}/certificate", files={"file": ("c.pdf", PDF)})
    anonymous = TestClient(create_app(s3_settings))
    r = anonymous.get(f"/api/registries/{one['public_id']}/certificate", follow_redirects=False)
    assert r.status_code == 401 and "location" not in r.headers and "X-Amz" not in r.text
    c, _ = customer(s3_settings, "DEV-2026-000002", "OTHER-CODE-2")                    # verified, but for registry two
    r = c.get(f"/api/registries/{one['public_id']}/certificate", follow_redirects=False)
    assert r.status_code == 401 and "location" not in r.headers


def test_public_responses_never_leak_keys_buckets_or_signed_urls(s3_settings, s3_client):
    admin = admin_client(s3_settings)
    reg = admin.post("/api/admin/registries", json=registry_payload()).json()
    admin.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c.pdf", PDF)})
    c, pid = customer(s3_settings)
    page = c.get(f"/api/registries/{pid}")
    text = json.dumps(page.json())
    assert page.json()["certificate"] == {"available": True, "content_type": "application/pdf", "label": "Star Dedication Certificate"}
    for forbidden in ("certificates/", BUCKET, "X-Amz", "amazonaws", "prod/", "size", "uploaded_at", '"contact_email"'):
        assert forbidden not in text, forbidden


def test_missing_object_is_a_clean_404(s3_settings, s3_client):
    admin = admin_client(s3_settings)
    reg = admin.post("/api/admin/registries", json=registry_payload()).json()
    admin.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c.pdf", PDF)})
    for key in objects(s3_client):
        s3_client.delete_object(Bucket=BUCKET, Key=key)                                  # object lost from the bucket
    c, pid = customer(s3_settings)
    r = c.get(f"/api/registries/{pid}/certificate", follow_redirects=False)
    assert r.status_code == 404 and r.json()["message"] == "Star Dedication Certificate currently unavailable."


def test_replacing_a_document_removes_the_old_object_only(s3_settings, s3_client):
    admin = admin_client(s3_settings)
    a = admin.post("/api/admin/registries", json=registry_payload()).json()
    b = admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV-2026-000002", registry_code="OTHER-CODE-2")).json()
    admin.post(f"/api/admin/registries/{a['id']}/certificate", files={"file": ("a.pdf", PDF)})
    admin.post(f"/api/admin/registries/{b['id']}/certificate", files={"file": ("b.pdf", PDF)})
    before_b = admin.get(f"/api/admin/registries/{b['id']}").json()
    admin.post(f"/api/admin/registries/{a['id']}/certificate", files={"file": ("a2.pdf", PDF2)})
    assert len(objects(s3_client)) == 2                                                  # a's old object gone, b's untouched
    assert admin.get(f"/api/admin/registries/{b['id']}").json()["certificate"] == before_b["certificate"]
    assert admin.get(f"/api/admin/registries/{a['id']}/certificate", follow_redirects=False).status_code == 302


def test_failed_database_update_removes_the_new_object_and_keeps_the_old(s3_settings, s3_client, monkeypatch):
    from app.database import registry_repository as rr
    admin = admin_client(s3_settings)
    reg = admin.post("/api/admin/registries", json=registry_payload()).json()
    admin.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c.pdf", PDF)})
    original = objects(s3_client)
    monkeypatch.setattr(rr.RegistryRepository, "update", lambda self, i, f: (_ for _ in ()).throw(RuntimeError("db down")))
    failing = TestClient(create_app(s3_settings), raise_server_exceptions=False)
    failing.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    r = failing.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c2.pdf", PDF2)})
    assert r.status_code == 500 and "db down" not in r.text
    assert objects(s3_client) == original                                                # no orphan, old file intact


def test_failed_upload_to_s3_changes_nothing_and_says_so(s3_settings, s3_client, monkeypatch):
    admin = admin_client(s3_settings)
    reg = admin.post("/api/admin/registries", json=registry_payload()).json()
    monkeypatch.setattr(admin.app.state.storage, "save_stream", lambda ext, fobj: (_ for _ in ()).throw(RuntimeError("S3 down")))
    r = admin.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c.pdf", PDF)})
    assert r.status_code == 502 and "Nothing was changed" in r.json()["message"] and "S3 down" not in r.text
    assert admin.get(f"/api/admin/registries/{reg['id']}").json()["certificate"]["available"] is False


def test_batch_save_uploads_to_s3_and_cleans_up_when_rejected(s3_settings, s3_client):
    admin = admin_client(s3_settings)
    records = [dict(registry_payload(registry_number=f"S3-BATCH-{i}", registry_code=f"S3CODE-{i}")) for i in (1, 2)]
    ok = admin.post("/api/admin/registries/batch", files=[("certificates", ("a.pdf", PDF)), ("registry_documents", ("b.pdf", PDF2))],
                    data={"records": json.dumps(records), "certificate_indexes": "[0]", "registry_document_indexes": "[1]"})
    assert ok.status_code == 201 and len(objects(s3_client)) == 2
    bad = admin.post("/api/admin/registries/batch", files=[("certificates", ("a.pdf", PDF))],
                     data={"records": json.dumps(records), "certificate_indexes": "[0]"})          # duplicate numbers
    assert bad.status_code == 422 and len(objects(s3_client)) == 2                                   # nothing orphaned


def test_s3_backend_requires_a_bucket_and_region(monkeypatch):
    from app.config import ConfigError, load_settings
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(ConfigError, match="S3_BUCKET"):
        load_settings()
    monkeypatch.setenv("STORAGE_BACKEND", "tape")
    with pytest.raises(ConfigError, match="STORAGE_BACKEND"):
        load_settings()
