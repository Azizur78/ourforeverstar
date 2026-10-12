"""Registry recovery. A public form that always answers the same way, and an admin-only review workflow."""
from __future__ import annotations

import logging
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..config import Settings
from ..database.connection import connect
from ..database.recovery_repository import STATUSES, RecoveryRepository
from ..database.registry_repository import RegistryRepository, utc_now
from ..deps import client_ip, get_settings, get_vault, require_admin
from ..schemas.registry import RecoveryRequestIn, RecoveryUpdate
from ..services import recovery as flow
from ..services.crypto import CodeVault

log = logging.getLogger("forever_star.recovery")

public_router = APIRouter(prefix="/api", tags=["recovery"])
router = APIRouter(prefix="/api/admin/recovery", tags=["admin-recovery"], dependencies=[Depends(require_admin)])

# One answer for every submission, so nobody can learn whether an email or registry number is on file.
GENERIC_RECEIVED = (
    "Thank you. We have received your request. Our team reviews every request personally and will contact you "
    "if we can help."
)


def get_repos(request: Request) -> Iterator[tuple[RecoveryRepository, RegistryRepository]]:
    conn = connect(request.app.state.settings.database_path)
    try:
        yield RecoveryRepository(conn), RegistryRepository(conn)
    finally:
        conn.close()


# ----------------------------------------------------------------- public

@public_router.post("/recovery-requests", status_code=202)
def submit_recovery_request(body: RecoveryRequestIn, request: Request, repos=Depends(get_repos)):
    limiter = request.app.state.recovery_limiter
    key = client_ip(request)
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(429, "Too many requests. Please try again later.", headers={"Retry-After": str(wait)})
    limiter.record(key)
    flow.submit(repos[0], body)
    return {"message": GENERIC_RECEIVED}


# ----------------------------------------------------------------- admin

def _registry_view(registry: dict | None) -> dict | None:
    if registry is None:
        return None
    return {
        "id": registry["id"], "registry_number": registry["registry_number"], "dedicated_to": registry["dedicated_to"],
        "dedicated_by": registry["dedicated_by"], "status": registry["status"],
        "contact_email": registry.get("contact_email"),
    }


def _summary(row: dict, registries: RegistryRepository) -> dict:
    registry = flow.find_registry(registries, row["registry_number"])
    return {
        "id": row["id"], "request_ref": row["request_ref"], "customer_name": row["customer_name"], "email": row["email"],
        "registry_number": row["registry_number"], "status": row["status"], "email_status": row["email_status"],
        "created_at": row["created_at"], "reviewed_at": row["reviewed_at"],
        "registry_match": flow.email_match(row, registry),
    }


def _detail(row: dict, registries: RegistryRepository) -> dict:
    registry = flow.find_registry(registries, row["registry_number"])
    address, kind = flow.recipient_for(row, registry)
    return {
        **_summary(row, registries),
        "message": row["message"], "admin_notes": row["admin_notes"], "verification_basis": row["verification_basis"],
        "reviewed_by": row["reviewed_by"], "completed_at": row["completed_at"], "email_sent_at": row["email_sent_at"],
        "email_error": row["email_error"], "updated_at": row["updated_at"],
        "allowed_transitions": sorted(flow.TRANSITIONS[row["status"]]),
        "registry": _registry_view(registry),
        "email_recipient": {"kind": kind, "masked": flow.mask_email(address)} if address else None,
    }


def _get_or_404(recovery: RecoveryRepository, request_id: int) -> dict:
    row = recovery.get(request_id)
    if not row:
        raise HTTPException(404, "Recovery request not found.")
    return row


@router.get("/summary")
def summary(repos=Depends(get_repos)):
    return repos[0].counts()


@router.get("")
def list_requests(
    status: str | None = Query(None, pattern="^(pending|under_review|approved|rejected|completed)$"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), repos=Depends(get_repos),
):
    recovery, registries = repos
    rows, total = recovery.list(status, page_size, (page - 1) * page_size)
    return {"items": [_summary(r, registries) for r in rows], "total": total, "page": page, "page_size": page_size,
            "statuses": list(STATUSES)}


@router.get("/{request_id}")
def get_request(request_id: int, repos=Depends(get_repos)):
    recovery, registries = repos
    return _detail(_get_or_404(recovery, request_id), registries)


@router.patch("/{request_id}")
def update_request(request_id: int, body: RecoveryUpdate, admin: str = Depends(require_admin), repos=Depends(get_repos)):
    recovery, registries = repos
    row = _get_or_404(recovery, request_id)
    try:
        updated = flow.apply_update(
            recovery, registries, row, admin, status=body.status, admin_notes=body.admin_notes,
            registry_number=body.registry_number, manually_verified=body.manually_verified,
            verification_note=body.verification_note,
        )
    except flow.RecoveryError as exc:
        raise HTTPException(exc.status_code, exc.message)
    return _detail(updated, registries)


@router.post("/{request_id}/send-email")
def send_details_email(
    request_id: int, request: Request, admin: str = Depends(require_admin), repos=Depends(get_repos),
    vault: CodeVault = Depends(get_vault), settings: Settings = Depends(get_settings),
):
    """Email the registry details to the verified address. Only an Approved request can be sent."""
    recovery, registries = repos
    row = _get_or_404(recovery, request_id)
    if row["status"] != "approved":
        raise HTTPException(409, "Only an approved request can be emailed.")
    registry = flow.find_registry(registries, row["registry_number"])
    address, _kind = flow.recipient_for(row, registry)
    if not address or registry is None:
        raise HTTPException(409, "There is no verified email address to send to. Add the customer's contact email "
                                 "to the registry, or verify the request manually.")
    sender = request.app.state.email_sender
    if sender is None:
        raise HTTPException(503, "Email is not configured on this server, so nothing was sent.")

    subject, text = flow.compose_details_email(row, registry, flow.decrypt_code(vault, registry), settings.public_base_url)
    try:
        sender.send(address, subject, text)
    except Exception as exc:  # noqa: BLE001  (record the class only; messages can echo server details)
        log.warning("Recovery email was not accepted by the mail server: %s", type(exc).__name__)
        recovery.update(request_id, {"email_status": "failed", "email_error": type(exc).__name__,
                                     "reviewed_by": admin, "reviewed_at": utc_now()})
        raise HTTPException(502, "The email could not be sent, so the request stays Approved. Check the email "
                                 "settings and try again.")
    now = utc_now()
    updated = recovery.update(request_id, {
        "email_status": "sent", "email_sent_at": now, "email_error": None, "status": "completed",
        "completed_at": now, "reviewed_by": admin, "reviewed_at": now,
    })
    return {**_detail(updated, registries), "notice": "The mail server accepted the email. The request is now Completed."}  # type: ignore[arg-type]
