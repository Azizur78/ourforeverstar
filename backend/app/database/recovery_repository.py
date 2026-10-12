"""Data access for registry-recovery requests."""
from __future__ import annotations

import secrets
import sqlite3
from typing import Any

from .registry_repository import utc_now

STATUSES = ("pending", "under_review", "approved", "rejected", "completed")
UPDATABLE = (
    "registry_number", "status", "admin_notes", "verification_basis", "reviewed_by", "reviewed_at", "completed_at",
    "email_status", "email_sent_at", "email_error",
)


class RecoveryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, *, customer_name: str, email: str, registry_number: str | None, message: str | None) -> dict[str, Any]:
        now = utc_now()
        ref = "RR-" + secrets.token_hex(5).upper()
        cur = self.conn.execute(
            "INSERT INTO recovery_requests (request_ref, customer_name, email, registry_number, message, status,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (ref, customer_name, email, registry_number, message, now, now),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)  # type: ignore[return-value, arg-type]

    def get(self, request_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM recovery_requests WHERE id = ?", (request_id,)).fetchone()
        return dict(row) if row else None

    def update(self, request_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        fields = {k: v for k, v in fields.items() if k in UPDATABLE}
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        self.conn.execute(f"UPDATE recovery_requests SET {assignments} WHERE id = :_id", {**fields, "_id": request_id})
        self.conn.commit()
        return self.get(request_id)

    def list(self, status: str | None, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        where, params = ("WHERE status = ?", [status]) if status else ("", [])
        total = self.conn.execute(f"SELECT COUNT(*) FROM recovery_requests {where}", params).fetchone()[0]
        rows = self.conn.execute(
            f"SELECT * FROM recovery_requests {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows], total

    def counts(self) -> dict[str, int]:
        found = dict(self.conn.execute("SELECT status, COUNT(*) FROM recovery_requests GROUP BY status").fetchall())
        return {status: found.get(status, 0) for status in STATUSES}

    def has_open_duplicate(self, email: str, registry_number: str | None, since: str) -> bool:
        """An unfinished request from the same email about the same registry in the recent past."""
        row = self.conn.execute(
            "SELECT 1 FROM recovery_requests WHERE email = ? COLLATE NOCASE AND COALESCE(registry_number, '') = ?"
            " AND status IN ('pending', 'under_review') AND created_at >= ? LIMIT 1",
            (email, registry_number or "", since),
        ).fetchone()
        return row is not None

    def count_recent_for_email(self, email: str, since: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM recovery_requests WHERE email = ? COLLATE NOCASE AND created_at >= ?", (email, since),
        ).fetchone()[0]
