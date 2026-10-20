"""What survives a restart, a wiped disk or a wiped database.

These mirror how Render behaves: a Free web service has an EPHEMERAL filesystem, so a spin-down, restart or redeploy
destroys everything on disk, which for this app is BOTH the SQLite database and the locally stored PDFs.
"""
import base64
import shutil
from dataclasses import replace

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.main import create_app
from conftest import ADMIN_PASSWORD, PDF, registry_payload

BUCKET = "persist-test-bucket"
NUMBER, CODE = "DEV-2026-000001", "TEST-CODE-1"


@pytest.fixture()
def s3(monkeypatch):
    for name, value in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_DEFAULT_REGION": "us-east-1"}.items():
        monkeypatch.setenv(name, value)
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def s3_settings(settings):
    return replace(settings, storage_backend="s3", s3_bucket=BUCKET, s3_region="us-east-1", s3_prefix="prod")


def keys(s3):
    return sorted(o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET).get("Contents", []))


def upload_certificate(settings):
    """One registry with one uploaded certificate, created through the real admin API."""
    admin = TestClient(create_app(settings))
    admin.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    reg = admin.post("/api/admin/registries", json=registry_payload()).json()
    assert admin.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c.pdf", PDF)}).status_code == 200
    return reg


def customer_download(settings, **kwargs):
    """A brand-new process (fresh app instance) and a brand-new visitor."""
    c = TestClient(create_app(settings))
    verified = c.post("/api/registries/verify", json={"registry_number": NUMBER, "registry_code": CODE})
    if verified.status_code != 200:
        return verified
    return c.get(f"/api/registries/{verified.json()['public_id']}/certificate", **kwargs)


def wipe_database(settings):
    for suffix in ("", "-wal", "-shm"):
        path = settings.database_path.with_name(settings.database_path.name + suffix)
        if path.exists():
            path.unlink()


# ------------------------------------------------------------------ persistent disk (paid plan + disk)

def test_records_and_pdfs_survive_a_restart_when_the_disk_persists(settings):
    upload_certificate(settings)
    r = customer_download(settings)                      # new app instance over the same database + upload folder
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"


# ------------------------------------------------------------------ today's staging behaviour (ephemeral disk)

def test_when_the_local_upload_folder_is_wiped_the_customer_gets_a_clear_unavailable_message(settings):
    upload_certificate(settings)
    shutil.rmtree(settings.upload_dir)
    r = customer_download(settings)
    assert r.status_code == 404 and "currently unavailable" in r.json()["message"]


def test_when_the_whole_disk_is_wiped_the_registry_itself_is_gone(settings):
    """Render Free: the SQLite file and the uploads vanish together, so the verification code stops working too."""
    upload_certificate(settings)
    shutil.rmtree(settings.upload_dir)
    wipe_database(settings)
    assert customer_download(settings).status_code == 404       # "Registry details could not be verified."


# ------------------------------------------------------------------ S3 alone is not enough while the database is ephemeral

def test_s3_keeps_the_object_but_a_wiped_database_orphans_it(settings, s3):
    cfg = s3_settings(settings)
    upload_certificate(cfg)
    assert len(keys(s3)) == 1
    wipe_database(cfg)
    assert customer_download(cfg).status_code == 404            # nothing points at the object any more
    assert len(keys(s3)) == 1                                   # the PDF still sits in the bucket, unreachable


def test_s3_with_a_persistent_database_survives_a_restart_and_a_wiped_local_disk(settings, s3):
    cfg = s3_settings(settings)
    upload_certificate(cfg)
    shutil.rmtree(cfg.upload_dir, ignore_errors=True)           # the container's disk is gone; S3 is not
    r = customer_download(cfg, follow_redirects=False)
    assert r.status_code == 302 and "X-Amz-Signature" in r.headers["location"]
    assert keys(s3)[0].startswith("prod/certificates/")


def test_documents_are_never_publicly_readable_in_the_bucket(settings, s3):
    cfg = s3_settings(settings)
    upload_certificate(cfg)
    key = keys(s3)[0]
    grants = s3.get_object_acl(Bucket=BUCKET, Key=key)["Grants"]
    assert not any("AllUsers" in str(g["Grantee"]) or "AuthenticatedUsers" in str(g["Grantee"]) for g in grants)


# ------------------------------------------------------------------ the staging seed on a database that is rebuilt every boot

def test_known_limitation_seed_replay_stores_a_new_object_on_every_boot_with_s3(settings, s3):
    """Seeded PDFs are re-saved under a fresh random key each time the database is rebuilt, so old objects orphan.

    Only matters if S3 is combined with an ephemeral database (the staging seed's whole purpose). With a persistent
    database the seed finds the record already present and stores nothing.
    """
    seed = {"records": [{**registry_payload(), "certificate": {"filename": "c.pdf", "content_base64": base64.b64encode(PDF).decode()}}]}
    cfg = replace(s3_settings(settings), staging_seed_b64=base64.b64encode(__import__("json").dumps(seed).encode()).decode())
    TestClient(create_app(cfg))
    assert len(keys(s3)) == 1
    TestClient(create_app(cfg))                                  # second boot, database intact -> nothing new
    assert len(keys(s3)) == 1
    wipe_database(cfg)
    TestClient(create_app(cfg))                                  # database rebuilt from the seed -> new object, old one orphaned
    assert len(keys(s3)) == 2
