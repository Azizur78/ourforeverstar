"""Request/response models. The write model is also reused by the one-time import script."""
from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["active", "inactive"]

REGISTRY_NUMBER_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-_/]{2,39}$")
REGISTRY_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{3,39}$")


def _clean(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _clean_optional(value: object) -> object:
    value = _clean(value)
    return None if value == "" else value


class RegistryWrite(BaseModel):
    """Full registry payload for create (POST) and replace (PUT)."""

    model_config = ConfigDict(extra="forbid")

    registry_number: str
    registry_code: str
    dedicated_to: Annotated[str, Field(min_length=1, max_length=120)]
    dedicated_by: Annotated[str, Field(min_length=1, max_length=120)]
    dedication_date: date
    occasion: Annotated[str | None, Field(max_length=80)] = None
    star_catalogue: Annotated[str | None, Field(max_length=80)] = None
    constellation: Annotated[str | None, Field(max_length=80)] = None
    distance: Annotated[str | None, Field(max_length=80)] = None
    dedication_message: Annotated[str | None, Field(max_length=2000)] = None
    status: Status = "active"

    @field_validator(
        "registry_number", "registry_code", "dedicated_to", "dedicated_by", mode="before"
    )
    @classmethod
    def _strip_required(cls, v: object) -> object:
        return _clean(v)

    @field_validator(
        "occasion", "star_catalogue", "constellation", "distance", "dedication_message", mode="before"
    )
    @classmethod
    def _strip_optional(cls, v: object) -> object:
        return _clean_optional(v)

    @field_validator("registry_number")
    @classmethod
    def _check_number(cls, v: str) -> str:
        v = v.upper()
        if not REGISTRY_NUMBER_RE.match(v):
            raise ValueError("Use 3-40 letters, numbers, hyphens, underscores or slashes (e.g. HIP-2026-000401).")
        return v

    @field_validator("registry_code")
    @classmethod
    def _check_code(cls, v: str) -> str:
        if not REGISTRY_CODE_RE.match(v):
            raise ValueError("Use 4-40 letters, numbers or hyphens.")
        return v


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registry_number: Annotated[str, Field(min_length=1, max_length=64)]
    registry_code: Annotated[str, Field(min_length=1, max_length=64)]

    @field_validator("registry_number", "registry_code", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return _clean(v)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: Annotated[str, Field(min_length=1, max_length=200)]
    new_password: Annotated[str, Field(min_length=1, max_length=200)]
    confirm_new_password: Annotated[str, Field(min_length=1, max_length=200)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, Field(min_length=1, max_length=100)]
    password: Annotated[str, Field(min_length=1, max_length=200)]
