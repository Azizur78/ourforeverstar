"""Customer-facing endpoints: verification, registry details and certificate."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import tokens
from ..config import Settings
from ..database.registry_repository import RegistryRepository
from ..deps import (
    REGISTRY_COOKIE, REGISTRY_PURPOSE, REGISTRY_TTL, client_ip, get_repo, get_settings, get_storage, get_vault,
)
from ..schemas.registry import VerifyRequest
from ..services.certificates import DocumentStorage
from ..services.crypto import CodeVault
from ..services.registry_service import to_public
from .files import document_response

router = APIRouter(prefix="/api/registries", tags=["registry"])

def _throttle_downloads(request: Request) -> None:
    """Every document request counts (allowed or not), so a stolen cookie or a script cannot hammer the storage."""
    limiter = request.app.state.download_limiter
    key = client_ip(request)
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(429, "Too many download requests. Please try again shortly.", headers={"Retry-After": str(wait)})
    limiter.record(key)


VERIFY_FAILED = "Registry details could not be verified."


def _active_registry_for(request: Request, public_id: str, repo: RegistryRepository,
                         settings: Settings) -> dict:
    subject = tokens.verify(settings.secret_key, REGISTRY_PURPOSE, request.cookies.get(REGISTRY_COOKIE))
    if subject != public_id:
        raise HTTPException(401, "Please verify your registry to continue.")
    row = repo.get_by_public_id(public_id)
    if not row or row["status"] != "active":
        raise HTTPException(404, "Registry not found.")
    return row


@router.post("/verify")
def verify_registry(
    body: VerifyRequest,
    request: Request,
    response: Response,
    repo: RegistryRepository = Depends(get_repo),
    vault: CodeVault = Depends(get_vault),
    settings: Settings = Depends(get_settings),
):
    limiter = request.app.state.verify_limiter
    key = client_ip(request)
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(wait)})

    row = repo.get_by_number(body.registry_number.upper())
    # Always hash so timing does not reveal whether the number exists.
    code_ok = vault.matches(body.registry_code, row["registry_code_hash"] if row else vault.hash("-"))
    if not (row and code_ok and row["status"] == "active"):
        limiter.record(key)
        raise HTTPException(404, VERIFY_FAILED)

    token = tokens.sign(settings.secret_key, REGISTRY_PURPOSE, row["public_id"], REGISTRY_TTL)
    response.set_cookie(
        REGISTRY_COOKIE, token, max_age=REGISTRY_TTL, httponly=True, samesite="lax",
        secure=settings.is_production, path="/api/registries",
    )
    return {"public_id": row["public_id"]}


@router.get("/{public_id}")
def get_registry(
    public_id: str,
    request: Request,
    repo: RegistryRepository = Depends(get_repo),
    vault: CodeVault = Depends(get_vault),
    settings: Settings = Depends(get_settings),
):
    return to_public(_active_registry_for(request, public_id, repo, settings), vault)


@router.get("/{public_id}/registry-document")
def get_registry_document(
    public_id: str,
    request: Request,
    download: bool = False,
    repo: RegistryRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
    storage: DocumentStorage = Depends(get_storage),
):
    _throttle_downloads(request)
    row = _active_registry_for(request, public_id, repo, settings)
    return document_response(row, storage, download, kind="registry_document")


@router.get("/{public_id}/certificate")
def get_certificate(
    public_id: str,
    request: Request,
    download: bool = False,
    repo: RegistryRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
    storage: DocumentStorage = Depends(get_storage),
):
    _throttle_downloads(request)
    row = _active_registry_for(request, public_id, repo, settings)
    return document_response(row, storage, download)
