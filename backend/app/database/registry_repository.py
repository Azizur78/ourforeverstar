"""Data access for registries. All SQL lives here so the database can be swapped later."""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any

UPDATABLE = (
    "registry_number", "registry_code", "registry_code_hash", "dedicated_to", "dedicated_by",
    "dedication_date", "occasion", "star_catalogue", "constellation", "distance",
    "dedication_message", "certificate_path", "status",
)


class DuplicateRegistryNumber(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class RegistryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        row = {**data, "public_id": secrets.token_urlsafe(12), "created_at": now, "updated_at": now}
        cols = ", ".join(row)
        marks = ", ".join(f":{k}" for k in row)
        try:
            cur = self.conn.execute(f"INSERT INTO registries ({cols}) VALUES ({marks})", row)
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            if "registry_number" in str(exc):
                raise DuplicateRegistryNumber() from exc
            raise
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, registry_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        fields = {k: v for k, v in fields.items() if k in UPDATABLE}
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        try:
            self.conn.execute(f"UPDATE registries SET {assignments} WHERE id = :_id", {**fields, "_id": registry_id})
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            if "registry_number" in str(exc):
                raise DuplicateRegistryNumber() from exc
            raise
        return self.get(registry_id)

    def _one(self, sql: str, params: tuple) -> dict[str, Any] | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def get(self, registry_id: int) -> dict[str, Any] | None:
        return self._one("SELECT * FROM registries WHERE id = ?", (registry_id,))

    def get_by_public_id(self, public_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM registries WHERE public_id = ?", (public_id,))

    def get_by_number(self, registry_number: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM registries WHERE registry_number = ?", (registry_number,))

    def search(self, q: str | None, code_hash: str | None, status: str | None,
               limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        params: list[Any] = []
        if q:
            like = f"%{_escape_like(q)}%"
            clause = ("(registry_number LIKE ? ESCAPE '\\' OR dedicated_to LIKE ? ESCAPE '\\' "
                      "OR dedicated_by LIKE ? ESCAPE '\\'")
            params += [like, like, like]
            if code_hash:
                clause += " OR registry_code_hash = ?"
                params.append(code_hash)
            where.append(clause + ")")
        if status:
            where.append("status = ?")
            params.append(status)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        total = self.conn.execute(f"SELECT COUNT(*) FROM registries {clause}", params).fetchone()[0]
        rows = self.conn.execute(
            f"SELECT * FROM registries {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows], total

    def counts(self) -> dict[str, int]:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(status = 'active'), 0) AS active, "
            "COALESCE(SUM(status = 'inactive'), 0) AS inactive FROM registries"
        ).fetchone()
        return {"total": row["total"], "active": row["active"], "inactive": row["inactive"]}
