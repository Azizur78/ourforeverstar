"""Request/response models. The write model is also reused by the one-time import script."""
from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["active", "inactive"]

REGISTRY_NUMBER_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-_/]{2,39}$")
REGISTRY_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{3,39}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")


def normalize_email(value: str | None) -> str | None:
    """Lower-cased, validated email or None. Raises ValueError for anything that is not a plain address."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address.")
    return value.lower()


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
    # Private: used only to verify recovery requests. Never returned by any customer-facing endpoint.
    contact_email: Annotated[str | None, Field(max_length=254)] = None
    status: Status = "active"

    @field_validator(
        "registry_number", "registry_code", "dedicated_to", "dedicated_by", mode="before"
    )
    @classmethod
    def _strip_required(cls, v: object) -> object:
        return _clean(v)

    @field_validator(
        "occasion", "star_catalogue", "constellation", "distance", "dedication_message", "contact_email", mode="before"
    )
    @classmethod
    def _strip_optional(cls, v: object) -> object:
        return _clean_optional(v)

    @field_validator("contact_email")
    @classmethod
    def _check_email(cls, v: str | None) -> str | None:
        return normalize_email(v)

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


# C0 control characters except tab (9), newline (10) and carriage return (13), plus DEL.
CONTROL_CHARS = re.compile("[" + "".join(map(chr, [*range(0, 9), 11, 12, *range(14, 32), 127])) + "]")


def _plain(value: object) -> object:
    """Trim and drop control characters (keeps newlines/tabs). Names and messages are rendered escaped by React."""
    return CONTROL_CHARS.sub("", value).strip() if isinstance(value, str) else value


class RecoveryRequestIn(BaseModel):
    """What a customer may submit. Nothing here proves identity; an admin decides by hand."""

    model_config = ConfigDict(extra="forbid")
    customer_name: Annotated[str, Field(min_length=2, max_length=120)]
    email: Annotated[str, Field(min_length=3, max_length=254)]
    registry_number: Annotated[str | None, Field(max_length=40)] = None
    message: Annotated[str | None, Field(max_length=1000)] = None
    website: Annotated[str | None, Field(max_length=200)] = None   # honeypot: real people leave it empty

    @field_validator("customer_name", "email", "registry_number", "message", "website", mode="before")
    @classmethod
    def _clean(cls, v: object) -> object:
        v = _plain(v)
        return None if v == "" and not isinstance(v, bool) else v

    @field_validator("customer_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v) or ""

    @field_validator("registry_number")
    @classmethod
    def _number(cls, v: str | None) -> str | None:
        return v.upper() if v else None


RecoveryStatus = Literal["pending", "under_review", "approved", "rejected", "completed"]


class RecoveryUpdate(BaseModel):
    """An admin's change to a request. All fields optional; only what is sent is changed."""

    model_config = ConfigDict(extra="forbid")
    status: RecoveryStatus | None = None
    registry_number: Annotated[str | None, Field(max_length=40)] = None   # link the request to a registry
    admin_notes: Annotated[str | None, Field(max_length=2000)] = None
    manually_verified: bool = False   # admin confirms identity through order/contact records
    verification_note: Annotated[str | None, Field(max_length=1000)] = None

    @field_validator("registry_number", mode="before")
    @classmethod
    def _number(cls, v: object) -> object:
        v = _plain(v)
        return v.upper() if isinstance(v, str) and v else None

    @field_validator("admin_notes", "verification_note", mode="before")
    @classmethod
    def _notes(cls, v: object) -> object:
        return _plain(v) or None
