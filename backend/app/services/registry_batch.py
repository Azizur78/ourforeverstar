"""Validation for creating several registries in one request (all-or-nothing).

Every problem is collected as {index, field, message} so the admin sees all of them at once and nothing is
written until the whole batch is clean. Messages never contain Registry Codes or internals.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastapi import UploadFile
from pydantic import ValidationError

from ..database.registry_repository import RegistryRepository
from ..schemas.registry import RegistryWrite
from .certificates import InvalidCertificate, inspect_stream

MAX_RECORDS = 50
MAX_CERTIFICATES = 20


class BatchRejected(Exception):
    def __init__(self, message: str, errors: list[dict[str, Any]], status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.errors = errors
        self.status_code = status_code

    def detail(self) -> dict[str, Any]:
        return {"message": self.message, "errors": self.errors}


@dataclass
class ValidatedBatch:
    payloads: list[RegistryWrite]
    # record index -> (upload, normalized extension, size in bytes)
    certificates: dict[int, tuple[UploadFile, str, int]]
    registry_documents: dict[int, tuple[UploadFile, str, int]]


def parse_records(raw: str) -> list[dict[str, Any]]:
    try:
        records = json.loads(raw)
    except ValueError:
        raise BatchRejected("The records could not be read. Please reload the page and try again.", []) from None
    if not isinstance(records, list) or not records or not all(isinstance(r, dict) for r in records):
        raise BatchRejected("Add at least one registry record.", [])
    if len(records) > MAX_RECORDS:
        raise BatchRejected(f"Please save at most {MAX_RECORDS} records at a time.", [])
    return records


def parse_certificate_map(raw: str, uploads: list[UploadFile], record_count: int,
                          what: str = "certificate") -> dict[int, UploadFile]:
    """Match each uploaded file to its record by the explicit index list sent with the request."""
    try:
        indexes = json.loads(raw or "[]")
    except ValueError:
        indexes = None
    ok = (isinstance(indexes, list) and len(indexes) == len(uploads)
          and all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < record_count for i in indexes)
          and len(set(indexes)) == len(indexes))
    if not ok:
        raise BatchRejected(f"The {what} files could not be matched to their records.", [])
    if len(uploads) > MAX_CERTIFICATES:
        raise BatchRejected(f"Please attach at most {MAX_CERTIFICATES} {what} files per batch.", [])
    return dict(zip(indexes, uploads))


def validate_batch(records: list[dict[str, Any]], uploads: dict[int, UploadFile], repo: RegistryRepository,
                   max_certificate_bytes: int, documents: dict[int, UploadFile] | None = None) -> ValidatedBatch:
    errors: list[dict[str, Any]] = []
    payloads: dict[int, RegistryWrite] = {}

    for i, item in enumerate(records):
        try:
            payloads[i] = RegistryWrite(**item)
        except ValidationError as exc:
            errors += [{"index": i, "field": str(e["loc"][0]) if e["loc"] else "record",
                        "message": str(e["msg"]).removeprefix("Value error, ")} for e in exc.errors()]
        except TypeError:
            errors.append({"index": i, "field": "record", "message": "This record is not valid."})

    by_number: dict[str, list[int]] = {}
    for i, payload in payloads.items():
        by_number.setdefault(payload.registry_number.upper(), []).append(i)
    for number, indexes in by_number.items():
        if len(indexes) > 1:
            errors += [{"index": i, "field": "registry_number", "message": "Duplicate registry number in this batch."}
                       for i in indexes]
        elif repo.get_by_number(number):
            errors.append({"index": indexes[0], "field": "registry_number", "message": "Registry number already exists."})

    extensions: dict[int, tuple[str, int]] = {}
    doc_extensions: dict[int, tuple[str, int]] = {}
    documents = documents or {}
    for field, files, found in (("certificate", uploads, extensions), ("registry_document", documents, doc_extensions)):
        for i, upload in files.items():
            try:
                found[i] = inspect_stream(upload.filename or "", upload.file, max_certificate_bytes)
            except InvalidCertificate as exc:
                errors.append({"index": i, "field": field, "message": exc.message})

    if errors:
        bad = len({e["index"] for e in errors})
        noun = "record needs" if bad == 1 else "records need"
        raise BatchRejected(f"{bad} {noun} attention. Nothing was saved.", sorted(errors, key=lambda e: e["index"]))
    return ValidatedBatch(
        payloads=[payloads[i] for i in range(len(records))],
        certificates={i: (uploads[i], *extensions[i]) for i in uploads},
        registry_documents={i: (documents[i], *doc_extensions[i]) for i in documents},
    )
