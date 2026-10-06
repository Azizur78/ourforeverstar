"""Registry code protection: HMAC for lookup/verification, Fernet for reversible display."""
from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet


def normalize_code(code: str) -> str:
    return code.strip().upper()


class CodeVault:
    def __init__(self, secret_key: str):
        self._hmac_key = hashlib.sha256(f"code-hmac:{secret_key}".encode()).digest()
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(f"code-enc:{secret_key}".encode()).digest())
        self._fernet = Fernet(fernet_key)

    def hash(self, code: str) -> str:
        return hmac.new(self._hmac_key, normalize_code(code).encode(), hashlib.sha256).hexdigest()

    def encrypt(self, code: str) -> str:
        return self._fernet.encrypt(code.strip().encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()

    def matches(self, code: str, stored_hash: str) -> bool:
        return hmac.compare_digest(self.hash(code), stored_hash)
