"""Translation between stored rows and API shapes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..schemas.registry import RegistryWrite
from .certificates import CONTENT_TYPES
from .crypto import CodeVault


def to_storage(payload: RegistryWrite, vault: CodeVault) -> dict[str, Any]:
    data = payload.model_dump()
    data["dedication_date"] = payload.dedication_date.isoformat()
    code = data.pop("registry_code")
    data["registry_code"] = vault.encrypt(code)
    data["registry_code_hash"] = vault.hash(code)
    return data


def _certificate_info(row: dict[str, Any]) -> dict[str, Any]:
    path = row.get("certificate_path")
    content_type = CONTENT_TYPES.get(Path(path).suffix.lower()) if path else None
    return {"available": bool(path), "content_type": content_type}


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
        "status": row["status"],
        "certificate": _certificate_info(row),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def to_public(row: dict[str, Any], vault: CodeVault) -> dict[str, Any]:
    """Customer-facing shape: no database id, status or internal fields."""
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
        "certificate": _certificate_info(row),
    }
