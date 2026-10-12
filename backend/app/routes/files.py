"""Shared document-serving helper for the public and admin routes.

Callers MUST have authorised the request before calling this. For S3 storage the result is a redirect to a
short-lived, read-only pre-signed URL; for local storage the file is streamed. Storage keys never leave the server.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, Response

from ..services.certificates import CONTENT_TYPES, DocumentStorage, safe_key
from ..services.registry_service import DOCUMENTS


def download_filename(prefix: str, registry_number: str, extension: str) -> str:
    """e.g. Star-Dedication-Certificate-OFS-2026-00035.pdf, restricted to filename-safe characters."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", f"{prefix}-{registry_number}{extension}")


def document_response(row: dict, storage: DocumentStorage, download: bool, *, kind: str = "certificate") -> Response:
    spec = DOCUMENTS[kind]
    key = safe_key(row.get(spec["column"]))
    if not key or not storage.exists(key):
        raise HTTPException(404, f"{spec['label']} currently unavailable.")
    extension = Path(key).suffix.lower()
    return storage.download(
        key,
        download_filename(spec["filename"], row["registry_number"], extension),
        CONTENT_TYPES.get(extension, "application/octet-stream"),
        attachment=download,
    )
