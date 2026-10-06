import os
import sys
from pathlib import Path

# Must be set before app.main is imported (it builds an app at import time).
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-definitely-long-enough-123")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.auth.passwords import hash_password
from app.config import Settings
from app.main import create_app

ADMIN_PASSWORD = "correct horse battery"

PDF = b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        app_env="test",
        database_path=tmp_path / "test.db",
        admin_username="admin",
        admin_password_hash=hash_password(ADMIN_PASSWORD),
        secret_key=os.environ["SECRET_KEY"],
        upload_dir=tmp_path / "uploads",
        instagram_url="https://instagram.com/example",
        cors_origins=("http://localhost:5173",),
        max_certificate_bytes=1024 * 1024,
        trust_proxy=False,
    )


@pytest.fixture()
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture()
def admin(client):
    r = client.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    return client


def registry_payload(**overrides):
    data = {
        "registry_number": "DEV-2026-000001",
        "registry_code": "TEST-CODE-1",
        "dedicated_to": "Test Person",
        "dedicated_by": "Test Sender",
        "dedication_date": "2026-02-14",
        "occasion": "Anniversary",
        "star_catalogue": "HIP 00000",
        "constellation": "Testudo",
        "distance": "100 light years",
        "dedication_message": "Development record.",
        "status": "active",
    }
    data.update(overrides)
    return data


@pytest.fixture()
def registry(admin):
    r = admin.post("/api/admin/registries", json=registry_payload())
    assert r.status_code == 201, r.text
    return r.json()


def fresh_client(settings):
    """A second, cookie-less client against the same app/database."""
    return TestClient(create_app(settings))
