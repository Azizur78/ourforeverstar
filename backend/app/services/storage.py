"""Chooses the document storage backend from the settings."""
from __future__ import annotations

from ..config import Settings
from .certificates import DocumentStorage, LocalCertificateStorage


def build_storage(settings: Settings) -> DocumentStorage:
    if settings.storage_backend == "s3":
        from .s3_storage import S3DocumentStorage  # imported lazily so local development needs no AWS SDK use
        return S3DocumentStorage(
            bucket=settings.s3_bucket, region=settings.s3_region, prefix=settings.s3_prefix,
            endpoint_url=settings.s3_endpoint_url, url_ttl_seconds=settings.download_url_ttl_seconds,
        )
    return LocalCertificateStorage(settings.upload_dir)
