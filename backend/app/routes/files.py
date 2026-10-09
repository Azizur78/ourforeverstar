"""Shared streaming helper for certificate and registry-document files (public and admin routes)."""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import FileResponse

from ..services.certificates import CONTENT_TYPES, CertificateStorage


def certificate_response(row: dict, storage: CertificateStorage, download: bool, *, kind: str = "certificate") -> FileResponse:
    column, label, prefix = (
        ("registry_document_path", "Registry document", "Forever-Star-Registry")
        if kind == "registry_document" else ("certificate_path", "Certificate", "Forever-Star-Certificate")
    )
    path = storage.open_path(row.get(column) or "")
    if path is None:
        raise HTTPException(404, f"{label} currently unavailable.")
    ext = path.suffix.lower()
    filename = f"{prefix}-{row['registry_number']}{ext}"
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
