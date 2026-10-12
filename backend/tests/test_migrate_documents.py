"""scripts/migrate_documents_to_s3.py: dry run by default, same keys, never deletes or overwrites."""
import sys
from dataclasses import replace
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.main import create_app
from conftest import ADMIN_PASSWORD, PDF, PDF2, registry_payload

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
BUCKET = "migrate-test-bucket"


@pytest.fixture()
def world(settings, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    for name, value in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_DEFAULT_REGION": "us-east-1"}.items():
        monkeypatch.setenv(name, value)
    # Existing production-style data: uploaded while the app still used local disk.
    admin = TestClient(create_app(settings))
    admin.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    reg = admin.post("/api/admin/registries", json=registry_payload()).json()
    admin.post(f"/api/admin/registries/{reg['id']}/certificate", files={"file": ("c.pdf", PDF)})
    admin.post(f"/api/admin/registries/{reg['id']}/registry-document", files={"file": ("r.pdf", PDF2)})
    # Point the environment at S3 and at the same database / upload folder.
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", BUCKET)
    monkeypatch.setenv("S3_REGION", "us-east-1")
    monkeypatch.setenv("S3_PREFIX", "prod")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{settings.database_path.as_posix()}")
    monkeypatch.setenv("UPLOAD_DIR", str(settings.upload_dir))
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client, settings, reg


def run(argv):
    sys.modules.pop("migrate_documents_to_s3", None)
    import migrate_documents_to_s3
    return migrate_documents_to_s3.main(argv)


def keys(client):
    return sorted(o["Key"] for o in client.list_objects_v2(Bucket=BUCKET).get("Contents", []))


def test_dry_run_copies_nothing(world, capsys):
    client, *_ = world
    assert run([]) == 0
    assert keys(client) == [] and "WOULD copy: 2" in capsys.readouterr().out


def test_commit_copies_under_the_same_keys_and_keeps_local_files(world, capsys):
    client, settings, _ = world
    assert run(["--commit"]) == 0
    stored = keys(client)
    assert len(stored) == 2 and all(k.startswith("prod/certificates/") for k in stored)
    assert len(list((settings.upload_dir / "certificates").glob("*.pdf"))) == 2          # local copies untouched
    assert "Copied: 2" in capsys.readouterr().out


def test_after_migration_the_app_serves_the_documents_from_s3_with_no_database_change(world):
    client, settings, reg = world
    run(["--commit"])
    s3_app = create_app(replace(settings, storage_backend="s3", s3_bucket=BUCKET, s3_region="us-east-1", s3_prefix="prod"))
    c = TestClient(s3_app)
    pid = c.post("/api/registries/verify", json={"registry_number": "DEV-2026-000001", "registry_code": "TEST-CODE-1"}).json()["public_id"]
    r = c.get(f"/api/registries/{pid}/certificate", follow_redirects=False)
    assert r.status_code == 302 and "X-Amz-Signature" in r.headers["location"]


def test_running_it_twice_is_harmless(world, capsys):
    client, *_ = world
    run(["--commit"])
    capsys.readouterr()
    assert run(["--commit"]) == 0
    assert "Copied: 0   Already in S3: 2" in capsys.readouterr().out and len(keys(client)) == 2


def test_it_never_overwrites_an_existing_object(world):
    client, settings, _ = world
    run(["--commit"])
    first = keys(client)[0]
    client.put_object(Bucket=BUCKET, Key=first, Body=b"%PDF-1.4 changed in S3 %%EOF")
    run(["--commit"])
    assert client.get_object(Bucket=BUCKET, Key=first)["Body"].read() == b"%PDF-1.4 changed in S3 %%EOF"


def test_missing_local_files_are_reported(world, capsys):
    client, settings, _ = world
    for f in (settings.upload_dir / "certificates").glob("*.pdf"):
        f.unlink()
    assert run(["--commit"]) == 1
    assert "[MISSING]" in capsys.readouterr().out


def test_it_refuses_to_run_without_the_s3_backend(world, monkeypatch, capsys):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    assert run([]) == 2
    assert "STORAGE_BACKEND=s3" in capsys.readouterr().err
