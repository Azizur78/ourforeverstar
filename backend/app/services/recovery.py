"""Manual registry recovery: what a request may do, how an admin may decide it, and what is emailed.

Rules this module enforces:
- A matching customer NAME never authorises anything.
- Approval needs a linked registry AND either (a) the submitted email equals the contact email already saved on that
  registry, or (b) the admin states they verified the person another way (with a written note).
- The saved contact email is never changed by this workflow.
- Details are emailed only to the registry's own contact email, or, when the registry has none, to the submitted
  address after a manual verification. Never to an unverified address.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..database.recovery_repository import RecoveryRepository
from ..database.registry_repository import RegistryRepository, utc_now
from ..schemas.registry import RecoveryRequestIn
from .crypto import CodeVault

TRANSITIONS: dict[str, set[str]] = {
    "pending": {"under_review", "rejected"},
    "under_review": {"approved", "rejected", "pending"},
    "approved": {"completed", "under_review"},
    "rejected": {"under_review"},
    "completed": set(),
}

DUPLICATE_WINDOW = timedelta(hours=24)
MAX_REQUESTS_PER_EMAIL_PER_DAY = 3


class RecoveryError(Exception):
    """A rule was not met. `message` is safe to show to the admin."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _since(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).isoformat(timespec="seconds")


def submit(repo: RecoveryRepository, data: RecoveryRequestIn) -> bool:
    """Store a customer's request. Returns whether a NEW row was created.

    The caller always gives the customer the same answer, so duplicates and spam are absorbed silently here.
    """
    if data.website:  # honeypot field filled in: a bot
        return False
    since = _since(DUPLICATE_WINDOW)
    if repo.has_open_duplicate(data.email, data.registry_number, since):
        return False
    if repo.count_recent_for_email(data.email, since) >= MAX_REQUESTS_PER_EMAIL_PER_DAY:
        return False
    repo.create(customer_name=data.customer_name, email=data.email, registry_number=data.registry_number,
                message=data.message)
    return True


def mask_email(address: str | None) -> str | None:
    if not address or "@" not in address:
        return None
    local, domain = address.split("@", 1)
    return f"{local[:1]}***@{domain[:1]}***{domain[domain.rfind('.'):]}"


def find_registry(registries: RegistryRepository, registry_number: str | None) -> dict[str, Any] | None:
    return registries.get_by_number(registry_number.upper()) if registry_number else None


def email_match(request: dict[str, Any], registry: dict[str, Any] | None) -> str:
    """'no_registry' | 'no_email_on_file' | 'match' | 'mismatch' (case-insensitive comparison of addresses only)."""
    if registry is None:
        return "no_registry"
    on_file = (registry.get("contact_email") or "").strip().lower()
    if not on_file:
        return "no_email_on_file"
    return "match" if on_file == request["email"].strip().lower() else "mismatch"


def recipient_for(request: dict[str, Any], registry: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """(address, kind). Details go to the registry's own address; the submitted one only after manual verification."""
    if registry is None:
        return None, None
    if (registry.get("contact_email") or "").strip():
        return registry["contact_email"].strip().lower(), "registry_contact"
    if request.get("verification_basis") == "manual":
        return request["email"], "submitted_after_manual_verification"
    return None, None


def apply_update(
    repo: RecoveryRepository, registries: RegistryRepository, request: dict[str, Any], admin: str, *,
    status: str | None, admin_notes: str | None, registry_number: str | None,
    manually_verified: bool, verification_note: str | None,
) -> dict[str, Any]:
    """Validate and apply an admin's decision. Raises RecoveryError when a rule is not met."""
    changes: dict[str, Any] = {"reviewed_by": admin, "reviewed_at": utc_now()}
    if admin_notes is not None:
        changes["admin_notes"] = admin_notes
    if registry_number:
        if request["status"] in ("approved", "completed"):
            raise RecoveryError("The linked registry cannot be changed after approval.")
        if not registries.get_by_number(registry_number.upper()):
            raise RecoveryError("No registry exists with that number.", 422)
        changes["registry_number"] = registry_number.upper()

    if status and status != request["status"]:
        if status not in TRANSITIONS[request["status"]]:
            raise RecoveryError(f"A {request['status'].replace('_', ' ')} request cannot be changed to {status.replace('_', ' ')}.")
        changes["status"] = status
        if status == "approved":
            candidate = {**request, **changes}
            registry = find_registry(registries, candidate.get("registry_number"))
            match = email_match(candidate, registry)
            if match == "no_registry":
                raise RecoveryError("Link this request to a registry before approving it.", 422)
            if match == "match":
                changes["verification_basis"] = "email_match"
            else:
                if not (manually_verified and verification_note):
                    reason = "The submitted email does not match the email on file for this registry" \
                        if match == "mismatch" else "This registry has no contact email on file"
                    raise RecoveryError(f"{reason}. Verify the customer another way and record how, to approve.", 422)
                stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                notes = changes.get("admin_notes", request.get("admin_notes")) or ""
                changes["admin_notes"] = f"{notes}\n[Manual verification by {admin}, {stamp}] {verification_note}".strip()
                changes["verification_basis"] = "manual"
        if status == "completed":
            changes["completed_at"] = utc_now()
        if status in ("pending", "under_review"):
            changes["verification_basis"] = None  # a reopened request must be verified again
    return repo.update(request["id"], changes)  # type: ignore[return-value]


def compose_details_email(request: dict[str, Any], registry: dict[str, Any], code: str, base_url: str) -> tuple[str, str]:
    """Subject and body. Contains the registry number and code, and a link to the website's own verification page.

    Document download links are deliberately NOT included: they are short-lived and only issued after verification.
    """
    link = f"{base_url}/verify" if base_url else "our website (choose Verify Registry)"
    body = (
        f"Hello {request['customer_name']},\n\n"
        "Thank you for contacting Our Forever Star. Here are the registry details you asked for.\n\n"
        f"Registry Number: {registry['registry_number']}\n"
        f"Registry Code:   {code}\n\n"
        f"To view your registry and download your documents, open {link} and enter both of the above.\n\n"
        "Please keep these details private. If you did not ask for this email, you can ignore it or message us on "
        "Instagram.\n\nWith warm wishes,\nOur Forever Star\n"
    )
    return "Your Our Forever Star registry details", body


def decrypt_code(vault: CodeVault, registry: dict[str, Any]) -> str:
    return vault.decrypt(registry["registry_code"])
