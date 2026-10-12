"""Databases created by earlier versions are upgraded in place, without losing anything."""
import os
import sqlite3

from fastapi.testclient import TestClient

from app.database.connection import ADDITIVE_COLUMNS, init_db
from app.main import create_app
from app.services.crypto import CodeVault
from conftest import ADMIN_PASSWORD
from test_registry_document import OLD_SCHEMA


def old_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    vault = CodeVault(os.environ["SECRET_KEY"])
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.execute("INSERT INTO registries (public_id, registry_number, registry_code, registry_code_hash, dedicated_to, dedicated_by,"
                 " dedication_date, certificate_path, status, created_at, updated_at) VALUES ('pid','OLD-0001',?,?,'To','By',"
                 "'2026-01-01','certificates/keep.png','active','t','t')", (vault.encrypt("OLDCODE-1"), vault.hash("OLDCODE-1")))
    conn.commit()
    conn.close()


def test_every_new_column_and_the_recovery_table_are_added(settings):
    old_database(settings.database_path)
    init_db(settings.database_path)
    init_db(settings.database_path)                                           # running it again changes nothing
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(registries)")}
    assert set(ADDITIVE_COLUMNS) <= columns
    assert {"contact_email", "certificate_size", "certificate_uploaded_at", "registry_document_size"} <= columns
    recovery = {r["name"] for r in conn.execute("PRAGMA table_info(recovery_requests)")}
    assert {"request_ref", "customer_name", "email", "registry_number", "message", "status", "admin_notes",
            "reviewed_by", "reviewed_at", "completed_at", "email_status", "email_sent_at", "email_error"} <= recovery
    row = conn.execute("SELECT * FROM registries").fetchone()
    assert row["registry_number"] == "OLD-0001" and row["certificate_path"] == "certificates/keep.png"
    assert row["contact_email"] is None and row["certificate_size"] is None
    conn.close()


def test_the_app_runs_on_an_upgraded_database_and_old_files_still_download(settings):
    old_database(settings.database_path)
    (settings.upload_dir / "certificates").mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / "certificates" / "keep.png").write_bytes(b"x")     # legacy, not a server-shaped key
    c = TestClient(create_app(settings))
    c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    item = c.get("/api/admin/registries").json()["items"][0]
    assert item["registry_number"] == "OLD-0001" and item["contact_email"] is None
    assert item["certificate"]["available"] is True and item["certificate"]["size"] is None   # metadata unknown for old files
    assert c.get("/api/admin/recovery/summary").json()["pending"] == 0
