"""Staging-only: restore the EXISTING test records on startup.

Render Free has an ephemeral filesystem, so the SQLite database and uploaded certificates vanish on every
restart/redeploy. When STAGING_SEED_FILE (a Render secret file) or STAGING_SEED_B64 is configured, the records it
contains are inserted if they are missing. Nothing is overwritten, nothing is created beyond what the file holds,
and the file is never part of the repository (it is produced locally by scripts/export_staging_bundle.py).
Registry Codes in the file are plaintext; they are hashed and encrypted with the staging SECRET_KEY on insert.

Error messages deliberately never include record values.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Any

from pydantic import ValidationError

from ..config import Settings
from ..database.connection import connect
from ..database.registry_repository import RegistryRepository
from ..schemas.registry import RegistryWrite
from .certificates import CertificateStorage, InvalidCertificate, validate_certificate
from .crypto import CodeVault
from .registry_service import to_storage

log = logging.getLogger("forever_star.seed")


class SeedError(RuntimeError):
    pass


def _load(settings: Settings) -> dict[str, Any] | None:
    if settings.staging_seed_file:
        if not settings.staging_seed_file.is_file():
            raise SeedError("STAGING_SEED_FILE is set but the file does not exist (add it as a Render secret file).")
        raw = settings.staging_seed_file.read_bytes()
    elif settings.staging_seed_b64:
        try:
            raw = base64.b64decode(settings.staging_seed_b64, validate=True)
        except (binascii.Error, ValueError):
            raise SeedError("STAGING_SEED_B64 is not valid base64.") from None
    else:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        raise SeedError("Staging seed is not valid JSON.") from None
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise SeedError('Staging seed must be an object with a "records" list.')
    return data


def apply_staging_seed(settings: Settings, vault: CodeVault, storage: CertificateStorage) -> dict[str, int]:
    data = _load(settings)
    if data is None:
        return {"added": 0, "skipped": 0}

    conn = connect(settings.database_path)
    repo = RegistryRepository(conn)
    added = skipped = 0
    try:
        for index, item in enumerate(data["records"], start=1):
            if not isinstance(item, dict):
                raise SeedError(f"Seed record #{index} is not an object.")
            item = dict(item)
            cert = item.pop("certificate", None)
            try:
                payload = RegistryWrite(**item)
            except (ValidationError, TypeError) as exc:
                fields = sorted({str(e["loc"][0]) for e in exc.errors()}) if isinstance(exc, ValidationError) else []
                raise SeedError(f"Seed record #{index} is invalid (fields: {', '.join(fields) or 'unknown'}).") from None
            if repo.get_by_number(payload.registry_number):
                skipped += 1
                continue
            row = repo.create(to_storage(payload, vault))
            added += 1
            if cert:
                try:
                    content = base64.b64decode(cert["content_base64"], validate=True)
                    extension = validate_certificate(cert["filename"], content, settings.max_certificate_bytes)
                except (KeyError, TypeError, binascii.Error, ValueError, InvalidCertificate):
                    raise SeedError(f"Seed record #{index} has an invalid certificate.") from None
                repo.update(row["id"], {"certificate_path": storage.save(extension, content)})
    finally:
        conn.close()
    log.warning("Staging seed applied: %d record(s) added, %d already present.", added, skipped)
    return {"added": added, "skipped": skipped}
