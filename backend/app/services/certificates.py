"""Certificate file storage. The interface lets an S3 backend replace local disk later."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

# extension -> (content type, magic-byte prefix)
ALLOWED_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}
CONTENT_TYPES = {ext: meta[0] for ext, meta in ALLOWED_TYPES.items()}


class InvalidCertificate(Exception):
    def __init__(self, message: str, too_large: bool = False):
        super().__init__(message)
        self.message = message
        self.too_large = too_large


class CertificateStorage(Protocol):
    def save(self, extension: str, data: bytes) -> str: ...
    def open_path(self, key: str) -> Path | None: ...
    def delete(self, key: str) -> None: ...


def validate_certificate(filename: str, data: bytes, max_bytes: int) -> str:
    """Return the normalized extension, or raise InvalidCertificate."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_TYPES:
        raise InvalidCertificate("Unsupported file type. Upload a PDF, PNG or JPG file.")
    if not data:
        raise InvalidCertificate("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise InvalidCertificate(
            f"File is too large. Maximum size is {max_bytes / (1024 * 1024):g} MB.", too_large=True
        )
    if not data.startswith(ALLOWED_TYPES[ext][1]):
        raise InvalidCertificate("File content does not match its file type.")
    return ".jpg" if ext == ".jpeg" else ext


class LocalCertificateStorage:
    SUBDIR = "certificates"

    def __init__(self, upload_dir: Path):
        self.root = (upload_dir / self.SUBDIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, extension: str, data: bytes) -> str:
        name = f"{uuid.uuid4().hex}{extension}"  # server-generated; user filename is never used
        (self.root / name).write_bytes(data)
        return f"{self.SUBDIR}/{name}"

    def open_path(self, key: str) -> Path | None:
        """Resolve a stored key to a file, refusing anything outside the certificate directory."""
        if not key:
            return None
        path = (self.root.parent / key).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            return None
        return path

    def delete(self, key: str) -> None:
        path = self.open_path(key)
        if path:
            path.unlink(missing_ok=True)
