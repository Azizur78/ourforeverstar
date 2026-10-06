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


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
