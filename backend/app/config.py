"""Application settings, loaded from environment variables (and the project-root .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
ROOT_DIR = BASE_DIR.parent

MIN_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_path: Path
    admin_username: str
    admin_password_hash: str
    secret_key: str
    upload_dir: Path
    instagram_url: str
    cors_origins: tuple[str, ...]
    max_certificate_bytes: int
    trust_proxy: bool
    # Which header carries the real client IP when TRUST_PROXY is on (rate limiting). On Render use CF-Connecting-IP.
    client_ip_header: str = "x-forwarded-for"
    # Single-service hosting: when set, FastAPI also serves the built React app from this folder.
    frontend_dist: Path | None = None
    # Staging only: keep search engines out.
    noindex: bool = False
    # Staging only: JSON file (or base64 JSON in STAGING_SEED_B64) with the existing test records, applied on startup.
    staging_seed_file: Path | None = None
    staging_seed_b64: str = ""
    # Document storage: "local" (development default) or "s3" (private bucket; production).
    storage_backend: str = "local"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_prefix: str = ""
    s3_endpoint_url: str = ""          # optional: an S3-compatible endpoint instead of AWS
    download_url_ttl_seconds: int = 300  # lifetime of a pre-signed download URL
    # Outgoing mail (recovery emails). Nothing is sent unless smtp_host and email_from are set.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    email_from: str = ""
    public_base_url: str = ""          # e.g. https://www.example.com, used for links inside emails

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (BASE_DIR / path).resolve()


def _database_path(url: str) -> Path:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ConfigError("DATABASE_URL must be a sqlite:/// URL in V1.")
    return _resolve_path(url[len(prefix):])


def load_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env", override=False)
    env = os.environ.get

    secret_key = env("SECRET_KEY", "")
    if len(secret_key) < MIN_SECRET_LENGTH:
        raise ConfigError(
            f"SECRET_KEY must be set to at least {MIN_SECRET_LENGTH} characters. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )

    app_env = env("APP_ENV", "development").lower()
    max_mb = float(env("MAX_CERTIFICATE_MB", "5"))
    origins = tuple(o.strip() for o in env("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip())

    storage_backend = env("STORAGE_BACKEND", "local").strip().lower()
    if storage_backend not in ("local", "s3"):
        raise ConfigError('STORAGE_BACKEND must be "local" or "s3".')
    if storage_backend == "s3" and not (env("S3_BUCKET", "").strip() and env("S3_REGION", "").strip()):
        raise ConfigError("STORAGE_BACKEND=s3 requires S3_BUCKET and S3_REGION (AWS credentials come from the standard AWS environment).")

    return Settings(
        app_env=app_env,
        database_path=_database_path(env("DATABASE_URL", "sqlite:///./data/forever_star.db")),
        admin_username=env("ADMIN_USERNAME", "admin"),
        admin_password_hash=env("ADMIN_PASSWORD_HASH", ""),
        secret_key=secret_key,
        upload_dir=_resolve_path(env("UPLOAD_DIR", "./uploads")),
        instagram_url=env("INSTAGRAM_URL", ""),
        cors_origins=origins,
        max_certificate_bytes=int(max_mb * 1024 * 1024),
        trust_proxy=env("TRUST_PROXY", "false").lower() == "true",
        client_ip_header=env("CLIENT_IP_HEADER", "x-forwarded-for").strip().lower(),
        frontend_dist=_resolve_path(env("FRONTEND_DIST")) if env("FRONTEND_DIST") else None,
        noindex=env("NOINDEX", "false").lower() == "true",
        staging_seed_file=_resolve_path(env("STAGING_SEED_FILE")) if env("STAGING_SEED_FILE") else None,
        staging_seed_b64=env("STAGING_SEED_B64", ""),
        storage_backend=storage_backend,
        s3_bucket=env("S3_BUCKET", "").strip(),
        s3_region=env("S3_REGION", "").strip(),
        s3_prefix=env("S3_PREFIX", "").strip().strip("/"),
        s3_endpoint_url=env("S3_ENDPOINT_URL", "").strip(),
        download_url_ttl_seconds=max(60, min(900, int(env("DOWNLOAD_URL_TTL_SECONDS", "300")))),
        smtp_host=env("SMTP_HOST", "").strip(),
        smtp_port=int(env("SMTP_PORT", "587")),
        smtp_username=env("SMTP_USERNAME", ""),
        smtp_password=env("SMTP_PASSWORD", ""),
        smtp_starttls=env("SMTP_STARTTLS", "true").lower() == "true",
        email_from=env("EMAIL_FROM", "").strip(),
        public_base_url=env("PUBLIC_BASE_URL", "").strip().rstrip("/"),
    )
