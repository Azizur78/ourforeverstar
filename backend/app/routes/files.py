"""Shared certificate-streaming helper for public and admin routes."""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import FileResponse

from ..services.certificates import CONTENT_TYPES, CertificateStorage


def certificate_response(row: dict, storage: CertificateStorage, download: bool) -> FileResponse:
    path = storage.open_path(row.get("certificate_path") or "")
    if path is None:
        raise HTTPException(404, "Certificate currently unavailable.")
    ext = path.suffix.lower()
    filename = f"Forever-Star-Certificate-{row['registry_number']}{ext}"
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path,
        media_type=CONTENT_TYPES.get(ext, "application/octet-stream"),
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
