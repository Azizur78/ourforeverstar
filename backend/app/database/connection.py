"""SQLite connection handling and schema creation."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS registries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id           TEXT NOT NULL UNIQUE,
    registry_number     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    registry_code       TEXT NOT NULL,            -- encrypted at rest
    registry_code_hash  TEXT NOT NULL,            -- HMAC used for verification/search
    dedicated_to        TEXT NOT NULL,
    dedicated_by        TEXT NOT NULL,
    dedication_date     TEXT NOT NULL,            -- ISO date
    occasion            TEXT,
    star_catalogue      TEXT,
    constellation       TEXT,
    distance            TEXT,
    dedication_message  TEXT,
    certificate_path    TEXT,                     -- relative storage key, never file bytes
    registry_document_path TEXT,                  -- optional uploaded registry document (same rules as the certificate)
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
-- Admin password set through the Admin UI. When a row exists it overrides ADMIN_PASSWORD_HASH.
CREATE TABLE IF NOT EXISTS admin_credentials (
    username       TEXT PRIMARY KEY,
    password_hash  TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
-- Customers who lost their registry details ask for help here. An admin reviews every request by hand.
CREATE TABLE IF NOT EXISTS recovery_requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_ref         TEXT NOT NULL UNIQUE,
    customer_name       TEXT NOT NULL,
    email               TEXT NOT NULL,
    registry_number     TEXT,
    message             TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'under_review', 'approved', 'rejected', 'completed')),
    admin_notes         TEXT,
    verification_basis  TEXT CHECK (verification_basis IN ('email_match', 'manual') OR verification_basis IS NULL),
    reviewed_by         TEXT,
    reviewed_at         TEXT,
    completed_at        TEXT,
    email_status        TEXT NOT NULL DEFAULT 'not_sent' CHECK (email_status IN ('not_sent', 'sent', 'failed')),
    email_sent_at       TEXT,
    email_error         TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recovery_status ON recovery_requests (status, created_at);
CREATE INDEX IF NOT EXISTS idx_recovery_email ON recovery_requests (email COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_registries_status ON registries (status);
CREATE INDEX IF NOT EXISTS idx_registries_code_hash ON registries (registry_code_hash);
CREATE INDEX IF NOT EXISTS idx_registries_dedicated_to ON registries (dedicated_to COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_registries_dedicated_by ON registries (dedicated_by COLLATE NOCASE);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    # One connection per request, used by one request at a time. FastAPI may run a request's dependencies
    # and handler on different worker threads, so the connection must be allowed to move between them.
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Columns added after the first release. Each is nullable, so existing rows stay valid.
ADDITIVE_COLUMNS = {
    "registry_document_path": "TEXT",          # second customer PDF (certificate of celestial registry)
    "certificate_size": "INTEGER",             # bytes, for the admin overview
    "certificate_uploaded_at": "TEXT",
    "registry_document_size": "INTEGER",
    "registry_document_uploaded_at": "TEXT",
    "contact_email": "TEXT",                   # private; used only to verify recovery requests, never shown to customers
}


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent upgrades for databases created by earlier versions."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(registries)")}
    for name, ddl in ADDITIVE_COLUMNS.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE registries ADD COLUMN {name} {ddl}")


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
