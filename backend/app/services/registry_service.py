"""Translation between stored rows and API shapes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..schemas.registry import RegistryWrite
from .certificates import CONTENT_TYPES
from .crypto import CodeVault

# The two customer PDFs. `column` holds the storage key; size/uploaded_at are admin-facing metadata.
DOCUMENTS = {
    "certificate": {
        "column": "certificate_path", "size": "certificate_size", "uploaded": "certificate_uploaded_at",
        "label": "Star Dedication Certificate", "filename": "Star-Dedication-Certificate",
    },
    "registry_document": {
        "column": "registry_document_path", "size": "registry_document_size", "uploaded": "registry_document_uploaded_at",
        "label": "Certificate of Celestial Registry", "filename": "Certificate-of-Celestial-Registry",
    },
}


def to_storage(payload: RegistryWrite, vault: CodeVault) -> dict[str, Any]:
    data = payload.model_dump()
    data["dedication_date"] = payload.dedication_date.isoformat()
    code = data.pop("registry_code")
    data["registry_code"] = vault.encrypt(code)
    data["registry_code_hash"] = vault.hash(code)
    return data


def _public_file_info(row: dict[str, Any], kind: str) -> dict[str, Any]:
    """Customers learn only whether a document exists and what it is; never a key, size or URL."""
    spec = DOCUMENTS[kind]
    path = row.get(spec["column"])
    content_type = CONTENT_TYPES.get(Path(path).suffix.lower()) if path else None
    return {"available": bool(path), "content_type": content_type, "label": spec["label"]}


def _admin_file_info(row: dict[str, Any], kind: str) -> dict[str, Any]:
    spec = DOCUMENTS[kind]
    return {**_public_file_info(row, kind), "size": row.get(spec["size"]), "uploaded_at": row.get(spec["uploaded"])}


def to_admin(row: dict[str, Any], vault: CodeVault) -> dict[str, Any]:
    return {
        "id": row["id"],
        "public_id": row["public_id"],
        "registry_number": row["registry_number"],
        "registry_code": vault.decrypt(row["registry_code"]),
        "dedicated_to": row["dedicated_to"],
        "dedicated_by": row["dedicated_by"],
        "dedication_date": row["dedication_date"],
        "occasion": row["occasion"],
        "star_catalogue": row["star_catalogue"],
        "constellation": row["constellation"],
        "distance": row["distance"],
        "dedication_message": row["dedication_message"],
        "contact_email": row.get("contact_email"),
        "status": row["status"],
        "certificate": _admin_file_info(row, "certificate"),
        "registry_document": _admin_file_info(row, "registry_document"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def to_public(row: dict[str, Any], vault: CodeVault) -> dict[str, Any]:
    """Customer-facing shape: no database id, status, contact email, storage key or internal field."""
    return {
        "public_id": row["public_id"],
        "registry_number": row["registry_number"],
        "registry_code": vault.decrypt(row["registry_code"]),
        "dedicated_to": row["dedicated_to"],
        "dedicated_by": row["dedicated_by"],
        "dedication_date": row["dedication_date"],
        "occasion": row["occasion"],
        "dedication_message": row["dedication_message"],
        "star": {
            "catalogue": row["star_catalogue"],
            "constellation": row["constellation"],
            "distance": row["distance"],
        },
        # Only whether one is saved, so the page knows whether to offer the recovery-email prompt.
        "has_contact_email": bool(row.get("contact_email")),
        "certificate": _public_file_info(row, "certificate"),
        "registry_document": _public_file_info(row, "registry_document"),
    }
