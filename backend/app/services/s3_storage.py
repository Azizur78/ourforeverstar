"""Private Amazon S3 storage for customer PDFs.

- The bucket stays private. Nothing here ever makes an object public.
- Uploads stream straight from the request to S3 (never fully buffered by the app) with server-side encryption.
- Downloads are authorised by the API first; only then is a short-lived, read-only pre-signed URL issued, as a
  redirect. The URL is a temporary bearer credential: it is never stored and never logged.

Minimum IAM permissions on the bucket's objects: s3:PutObject, s3:GetObject, s3:DeleteObject
(optionally s3:ListBucket so a missing object reads as 404 instead of 403).
"""
from __future__ import annotations

import logging
import re
from typing import BinaryIO

from fastapi import Response
from fastapi.responses import RedirectResponse

from .certificates import CONTENT_TYPES, new_key, safe_key

log = logging.getLogger("forever_star.storage")
_MISSING = {"404", "NoSuchKey", "NotFound"}


class S3DocumentStorage:
    def __init__(self, bucket: str, region: str, prefix: str = "", endpoint_url: str = "",
                 url_ttl_seconds: int = 300, client=None):
        self.bucket = bucket
        self.prefix = f"{prefix.strip('/')}/" if prefix.strip("/") else ""
        self.ttl = url_ttl_seconds
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client(
                "s3", region_name=region, endpoint_url=endpoint_url or None,
                config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
            )
        self.client = client

    def _object_key(self, key: str) -> str:
        valid = safe_key(key)
        if not valid:
            raise ValueError("Invalid storage key.")
        return f"{self.prefix}{valid}"

    @staticmethod
    def _content_type(key: str) -> str:
        return CONTENT_TYPES.get("." + key.rsplit(".", 1)[-1], "application/octet-stream")

    def put(self, key: str, fileobj: BinaryIO) -> None:
        """Store a stream under an EXISTING valid key (used when migrating files that already have a key)."""
        fileobj.seek(0)
        self.client.upload_fileobj(
            fileobj, self.bucket, self._object_key(key),
            ExtraArgs={"ContentType": self._content_type(key), "ServerSideEncryption": "AES256",
                       "CacheControl": "private, no-store"},
        )

    def save_stream(self, extension: str, fileobj: BinaryIO) -> str:
        key = new_key(extension)
        self.put(key, fileobj)
        return key

    def save(self, extension: str, data: bytes) -> str:
        import io
        return self.save_stream(extension, io.BytesIO(data))

    def exists(self, key: str) -> bool:
        if not safe_key(key):
            return False
        from botocore.exceptions import ClientError
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._object_key(key))
            return True
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in _MISSING:
                return False
            if code == "403":
                # Without s3:ListBucket, S3 answers 403 for an absent key. Log the class of problem only.
                log.warning("S3 head_object returned 403 (missing object or missing permission).")
                return False
            raise

    def delete(self, key: str) -> None:
        if safe_key(key):
            self.client.delete_object(Bucket=self.bucket, Key=self._object_key(key))

    def download(self, key: str, filename: str, content_type: str, *, attachment: bool) -> Response:
        safe_name = re.sub(r'[^A-Za-z0-9._-]', "_", filename)
        url = self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": self._object_key(key),
                "ResponseContentDisposition": f'{"attachment" if attachment else "inline"}; filename="{safe_name}"',
                "ResponseContentType": content_type,
            },
            ExpiresIn=self.ttl,
        )
        # 302 to the signed URL. no-store + no-referrer keep the credential out of caches and referrers.
        return RedirectResponse(url, status_code=302,
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
