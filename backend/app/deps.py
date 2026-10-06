"""FastAPI dependencies and small request helpers."""
from __future__ import annotations

import hashlib
import hmac
from typing import Iterator

from fastapi import Depends, HTTPException, Request, status

from .auth import tokens
from .config import Settings
from .database.connection import connect
from .database.admin_repository import AdminCredentialStore
from .database.registry_repository import RegistryRepository
from .services.certificates import CertificateStorage
from .services.crypto import CodeVault

ADMIN_COOKIE = "fs_admin_session"
ADMIN_PURPOSE = "admin-session"
ADMIN_TTL = 8 * 60 * 60

REGISTRY_COOKIE = "fs_registry_access"
REGISTRY_PURPOSE = "registry-access"
REGISTRY_TTL = 60 * 60


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_vault(request: Request) -> CodeVault:
    return request.app.state.vault


def get_storage(request: Request) -> CertificateStorage:
    return request.app.state.storage


def get_repo(request: Request) -> Iterator[RegistryRepository]:
    conn = connect(request.app.state.settings.database_path)
    try:
        yield RegistryRepository(conn)
    finally:
        conn.close()


def get_admin_store(request: Request) -> Iterator[AdminCredentialStore]:
    conn = connect(request.app.state.settings.database_path)
    try:
        yield AdminCredentialStore(conn, request.app.state.settings)
    finally:
        conn.close()


def admin_subject(username: str, password_hash: str) -> str:
    """Session subject bound to the current password, so a password change ends all older sessions."""
    return f"{username}:{hashlib.sha256(password_hash.encode()).hexdigest()[:16]}"


def client_ip(request: Request) -> str:
    settings = request.app.state.settings
    if settings.trust_proxy:
        raw = request.headers.get(settings.client_ip_header)
        if raw:
            # X-Forwarded-For: clients can prepend fake entries, so only the entry appended by our own proxy
            # (the rightmost) is trusted. Single-value headers such as CF-Connecting-IP are used as-is.
            value = raw.split(",")[-1] if settings.client_ip_header == "x-forwarded-for" else raw
            if value.strip():
                return value.strip()
    return request.client.host if request.client else "unknown"


def require_admin(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: AdminCredentialStore = Depends(get_admin_store),
) -> str:
    subject = tokens.verify(settings.secret_key, ADMIN_PURPOSE, request.cookies.get(ADMIN_COOKIE))
    current = store.active_hash()
    if not subject or not current or not hmac.compare_digest(subject, admin_subject(settings.admin_username, current)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")
    return settings.admin_username
