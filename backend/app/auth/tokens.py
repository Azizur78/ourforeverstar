"""Small signed, expiring tokens for cookies (HMAC-SHA256). Purpose strings isolate token types."""
from __future__ import annotations

import base64
import hashlib
import hmac
import time


def _sig(secret: str, purpose: str, payload: str) -> str:
    key = hashlib.sha256(f"token:{purpose}:{secret}".encode()).digest()
    return base64.urlsafe_b64encode(hmac.new(key, payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def sign(secret: str, purpose: str, subject: str, ttl_seconds: int) -> str:
    payload = f"{subject}|{int(time.time()) + ttl_seconds}"
    return f"{payload}|{_sig(secret, purpose, payload)}"


def verify(secret: str, purpose: str, token: str | None) -> str | None:
    """Return the subject if the token is authentic and unexpired, else None."""
    if not token:
        return None
    try:
        subject, expires, signature = token.rsplit("|", 2)
        if not hmac.compare_digest(signature, _sig(secret, purpose, f"{subject}|{expires}")):
            return None
        return subject if int(expires) > time.time() else None
    except ValueError:
        return None
