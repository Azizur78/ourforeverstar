"""Admin endpoints. Every route except login requires a valid admin session."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile

from ..auth import tokens
from ..auth.passwords import DUMMY_HASH, hash_password, verify_password
from ..config import Settings
from ..database.admin_repository import AdminCredentialStore
from ..database.registry_repository import DuplicateRegistryNumber, RegistryRepository
from ..deps import (
    ADMIN_COOKIE, ADMIN_PURPOSE, ADMIN_TTL, admin_subject, client_ip, get_admin_store, get_repo, get_settings, get_storage, get_vault, require_admin,
)
from ..schemas.registry import ChangePasswordRequest, LoginRequest, RegistryWrite, StatusUpdate
from ..services.certificates import CertificateStorage, InvalidCertificate, validate_certificate
from ..services.crypto import CodeVault
from ..services.registry_batch import (
    MAX_CERTIFICATES, BatchRejected, parse_certificate_map, parse_records, validate_batch,
)
from ..services.registry_service import to_admin, to_storage
from .files import certificate_response

public_router = APIRouter(prefix="/api/admin", tags=["admin-auth"])
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


def _set_session_cookie(response: Response, settings: Settings, password_hash: str) -> None:
    token = tokens.sign(settings.secret_key, ADMIN_PURPOSE, admin_subject(settings.admin_username, password_hash), ADMIN_TTL)
    response.set_cookie(
        ADMIN_COOKIE, token, max_age=ADMIN_TTL, httponly=True, samesite="strict",
        secure=settings.is_production, path="/api/admin",
    )


def _duplicate() -> HTTPException:
    return HTTPException(409, detail={"message": "This Registry Number already exists.", "field": "registry_number"})


def _get_or_404(repo: RegistryRepository, registry_id: int) -> dict:
    row = repo.get(registry_id)
    if not row:
        raise HTTPException(404, "Registry not found.")
    return row


# ---- auth ---------------------------------------------------------------

@public_router.post("/login")
def login(body: LoginRequest, request: Request, response: Response,
          settings: Settings = Depends(get_settings), store: AdminCredentialStore = Depends(get_admin_store)):
    limiter = request.app.state.login_limiter
    key = client_ip(request)
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(wait)})

    active_hash = store.active_hash()
    password_ok = verify_password(body.password, active_hash or DUMMY_HASH)
    username_ok = body.username == settings.admin_username
    if not (password_ok and username_ok and active_hash):
        limiter.record(key)
        raise HTTPException(401, "Invalid username or password.")

    limiter.reset(key)
    _set_session_cookie(response, settings, active_hash)
    return {"username": settings.admin_username}


@public_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE, path="/api/admin")
    return {"ok": True}


@router.get("/me")
def me(username: str = Depends(require_admin)):
    return {"username": username}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    store: AdminCredentialStore = Depends(get_admin_store),
):
    """Server-side password change. Only the new scrypt hash is stored; nothing secret is returned."""
    limiter = request.app.state.password_limiter
    key = client_ip(request)
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(wait)})

    if body.new_password != body.confirm_new_password:
        raise HTTPException(422, detail={"message": "New passwords do not match.", "field": "confirm_new_password"})
    if not (MIN_PASSWORD_LENGTH <= len(body.new_password) <= MAX_PASSWORD_LENGTH) or not body.new_password.strip():
        raise HTTPException(422, detail={
            "message": "Password does not meet the required security requirements.",
            "field": "new_password",
            "hint": f"Use {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters.",
        })
    if not verify_password(body.current_password, store.active_hash()):
        limiter.record(key)
        raise HTTPException(400, detail={"message": "Current password is incorrect.", "field": "current_password"})
    if body.new_password == body.current_password:
        raise HTTPException(422, detail={
            "message": "New password must be different from your current password.", "field": "new_password",
        })

    new_hash = hash_password(body.new_password)
    store.set_hash(new_hash)
    limiter.reset(key)
    # Keep this admin signed in; every older session (bound to the old hash) stops working.
    _set_session_cookie(response, settings, new_hash)
    return {"message": "Password changed successfully."}


# ---- registries ----------------------------------------------------------

@router.get("/stats")
def stats(repo: RegistryRepository = Depends(get_repo)):
    return repo.counts()


@router.get("/registries")
def list_registries(
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern="^(active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    repo: RegistryRepository = Depends(get_repo),
    vault: CodeVault = Depends(get_vault),
):
    q = q.strip() if q else None
    rows, total = repo.search(q, vault.hash(q) if q else None, status, page_size, (page - 1) * page_size)
    return {"items": [to_admin(r, vault) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/registries", status_code=201)
def create_registry(body: RegistryWrite, repo: RegistryRepository = Depends(get_repo),
                    vault: CodeVault = Depends(get_vault)):
    if repo.get_by_number(body.registry_number):
        raise _duplicate()
    try:
        row = repo.create(to_storage(body, vault))
    except DuplicateRegistryNumber:
        raise _duplicate()
    return to_admin(row, vault)


@router.post("/registries/batch", status_code=201)
def create_registries_batch(
    request: Request,
    records: str = Form(...),
    certificate_indexes: str = Form("[]"),
    certificates: list[UploadFile] = File(default=[]),
    registry_document_indexes: str = Form("[]"),
    registry_documents: list[UploadFile] = File(default=[]),
    repo: RegistryRepository = Depends(get_repo),
    vault: CodeVault = Depends(get_vault),
    settings: Settings = Depends(get_settings),
    storage: CertificateStorage = Depends(get_storage),
):
    """Create several registries (each with an optional certificate) in one all-or-nothing request.

    multipart/form-data: `records` = JSON list of registry objects; `certificates` = files, and
    `certificate_indexes` = JSON list giving the record index of each file, in the same order. Registry documents
    work the same way through `registry_documents` / `registry_document_indexes`.
    """
    limit = settings.max_certificate_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit * MAX_CERTIFICATES * 2 + 1024 * 1024:
        raise HTTPException(413, "The upload is too large. Please save fewer certificates at once.")
    try:
        parsed = parse_records(records)
        uploads = parse_certificate_map(certificate_indexes, certificates, len(parsed))
        doc_uploads = parse_certificate_map(registry_document_indexes, registry_documents, len(parsed), "registry document")
        batch = validate_batch(parsed, uploads, repo, limit, doc_uploads)
    except BatchRejected as exc:
        raise HTTPException(exc.status_code, detail=exc.detail())

    saved_keys: list[str] = []
    try:
        rows = []
        for i, payload in enumerate(batch.payloads):
            row = to_storage(payload, vault)
            if i in batch.certificates:
                upload, extension = batch.certificates[i]
                key = storage.save(extension, upload.file.read())
                saved_keys.append(key)
                row["certificate_path"] = key
            if i in batch.registry_documents:
                upload, extension = batch.registry_documents[i]
                key = storage.save(extension, upload.file.read())
                saved_keys.append(key)
                row["registry_document_path"] = key
            rows.append(row)
        created = repo.create_many(rows)
    except DuplicateRegistryNumber:
        # Lost a race with another request between validation and insert; nothing was written.
        for key in saved_keys:
            storage.delete(key)
        raise HTTPException(409, detail={
            "message": "A registry number in this batch was just added by someone else. Nothing was saved.",
            "errors": [],
        })
    except Exception:
        for key in saved_keys:
            storage.delete(key)
        raise
    return {"count": len(created), "created": [to_admin(r, vault) for r in created]}


@router.get("/registries/{registry_id}")
def get_registry(registry_id: int, repo: RegistryRepository = Depends(get_repo),
                 vault: CodeVault = Depends(get_vault)):
    return to_admin(_get_or_404(repo, registry_id), vault)


@router.put("/registries/{registry_id}")
def update_registry(registry_id: int, body: RegistryWrite, repo: RegistryRepository = Depends(get_repo),
                    vault: CodeVault = Depends(get_vault)):
    _get_or_404(repo, registry_id)
    existing = repo.get_by_number(body.registry_number)
    if existing and existing["id"] != registry_id:
        raise _duplicate()
    try:
        row = repo.update(registry_id, to_storage(body, vault))
    except DuplicateRegistryNumber:
        raise _duplicate()
    return to_admin(row, vault)  # type: ignore[arg-type]


@router.patch("/registries/{registry_id}/status")
def set_status(registry_id: int, body: StatusUpdate, repo: RegistryRepository = Depends(get_repo),
               vault: CodeVault = Depends(get_vault)):
    _get_or_404(repo, registry_id)
    return to_admin(repo.update(registry_id, {"status": body.status}), vault)  # type: ignore[arg-type]


@router.delete("/registries/{registry_id}")
def deactivate_registry(registry_id: int, repo: RegistryRepository = Depends(get_repo),
                        vault: CodeVault = Depends(get_vault)):
    """Registries are never hard-deleted in V1; DELETE deactivates."""
    _get_or_404(repo, registry_id)
    return to_admin(repo.update(registry_id, {"status": "inactive"}), vault)  # type: ignore[arg-type]


# ---- certificate -----------------------------------------------------------

def _replace_file(registry_id: int, column: str, request: Request, file: UploadFile, repo: RegistryRepository,
                  vault: CodeVault, settings: Settings, storage: CertificateStorage) -> dict:
    """Validate an upload, store it, point the registry at it and delete the file it replaces."""
    row = _get_or_404(repo, registry_id)
    limit = settings.max_certificate_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise HTTPException(413, f"File is too large. Maximum size is {limit / (1024 * 1024):g} MB.")
    data = file.file.read(limit + 1)
    try:
        extension = validate_certificate(file.filename or "", data, limit)
    except InvalidCertificate as exc:
        raise HTTPException(413 if exc.too_large else 415, exc.message)

    new_key = storage.save(extension, data)
    updated = repo.update(registry_id, {column: new_key})
    if row.get(column):
        storage.delete(row[column])
    return to_admin(updated, vault)  # type: ignore[arg-type]


@router.post("/registries/{registry_id}/certificate")
def upload_certificate(
    registry_id: int,
    request: Request,
    file: UploadFile = File(...),
    repo: RegistryRepository = Depends(get_repo),
    vault: CodeVault = Depends(get_vault),
    settings: Settings = Depends(get_settings),
    storage: CertificateStorage = Depends(get_storage),
):
    return _replace_file(registry_id, "certificate_path", request, file, repo, vault, settings, storage)


@router.get("/registries/{registry_id}/certificate")
def view_certificate(registry_id: int, download: bool = False, repo: RegistryRepository = Depends(get_repo),
                     storage: CertificateStorage = Depends(get_storage)):
    return certificate_response(_get_or_404(repo, registry_id), storage, download)


@router.post("/registries/{registry_id}/registry-document")
def upload_registry_document(
    registry_id: int,
    request: Request,
    file: UploadFile = File(...),
    repo: RegistryRepository = Depends(get_repo),
    vault: CodeVault = Depends(get_vault),
    settings: Settings = Depends(get_settings),
    storage: CertificateStorage = Depends(get_storage),
):
    """Attach the registry document (PDF, PNG or JPG) to a registry. Same rules as the certificate."""
    return _replace_file(registry_id, "registry_document_path", request, file, repo, vault, settings, storage)


@router.get("/registries/{registry_id}/registry-document")
def view_registry_document(registry_id: int, download: bool = False, repo: RegistryRepository = Depends(get_repo),
                           storage: CertificateStorage = Depends(get_storage)):
    return certificate_response(_get_or_404(repo, registry_id), storage, download, kind="registry_document")
