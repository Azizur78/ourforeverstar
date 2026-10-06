"""scrypt password hashing (stdlib only). Format: scrypt:N:r:p:salt_b64:hash_b64"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

_N, _R, _P = 2**14, 8, 1


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt:{_N}:{_R}:{_P}:{_b64(salt)}:{_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split(":")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(digest, _unb64(expected))
    except (ValueError, TypeError):
        return False


# Used to keep login timing similar when the username does not match.
DUMMY_HASH = hash_password("not-a-real-password")
