"""Admin credential storage. Only password hashes are ever stored."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..config import Settings


class AdminCredentialStore:
    def __init__(self, conn: sqlite3.Connection, settings: Settings):
        self.conn = conn
        self.settings = settings

    def active_hash(self) -> str:
        """Hash set via the Admin UI if there is one, otherwise the initial ADMIN_PASSWORD_HASH."""
        row = self.conn.execute(
            "SELECT password_hash FROM admin_credentials WHERE username = ?", (self.settings.admin_username,)
        ).fetchone()
        return row["password_hash"] if row else self.settings.admin_password_hash

    def set_hash(self, password_hash: str) -> None:
        self.conn.execute(
            "INSERT INTO admin_credentials (username, password_hash, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash, updated_at = excluded.updated_at",
            (self.settings.admin_username, password_hash, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.conn.commit()
