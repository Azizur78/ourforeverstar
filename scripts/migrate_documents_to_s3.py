"""One-time copy of the customer PDFs from local disk to the private S3 bucket.

    python scripts/migrate_documents_to_s3.py            # dry run: reports what WOULD be copied
    python scripts/migrate_documents_to_s3.py --commit   # copies the files

Requires STORAGE_BACKEND=s3 (plus S3_BUCKET, S3_REGION and AWS credentials) in the environment.

Why this is safe and simple:
- The database stores keys such as "certificates/<32 hex>.pdf". The S3 object name is the (optional) prefix plus that very
  same key, so NOTHING in the database changes.
- Existing objects are never overwritten and local files are never deleted. Delete the local copies yourself only after
  you have confirmed the report below and tested a download.
- Nothing is printed except counts and file keys (the keys are random, not customer data).
"""
import _bootstrap  # noqa: F401
import argparse
import sqlite3
import sys

from app.config import load_settings
from app.services.certificates import LocalCertificateStorage, safe_key
from app.services.storage import build_storage


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", action="store_true", help="actually copy (default is a dry run)")
    args = ap.parse_args(argv)

    settings = load_settings()
    if settings.storage_backend != "s3":
        print("Set STORAGE_BACKEND=s3 (and S3_BUCKET / S3_REGION) first; this script copies local files INTO S3.", file=sys.stderr)
        return 2

    local = LocalCertificateStorage(settings.upload_dir)
    remote = build_storage(settings)
    conn = sqlite3.connect(settings.database_path)
    keys = []
    for column in ("certificate_path", "registry_document_path"):
        keys += [r[0] for r in conn.execute(f"SELECT {column} FROM registries WHERE {column} IS NOT NULL AND {column} != ''")]
    conn.close()

    copied = already = missing = skipped = 0
    for key in keys:
        if not safe_key(key):
            skipped += 1
            print(f"  [SKIPPED] unexpected key format: {key!r}")
            continue
        path = local.open_path(key)
        if path is None:
            if remote.exists(key):
                already += 1
            else:
                missing += 1
                print(f"  [MISSING] no local file and not in S3: {key}")
            continue
        if remote.exists(key):
            already += 1
            continue
        if args.commit:
            with path.open("rb") as fh:
                remote.put(key, fh)  # type: ignore[attr-defined]
        copied += 1

    verb = "Copied" if args.commit else "WOULD copy"
    print(f"\nDocuments referenced in the database: {len(keys)}")
    print(f"{verb}: {copied}   Already in S3: {already}   Missing everywhere: {missing}   Skipped (odd key): {skipped}")
    if not args.commit:
        print("Dry run only. Re-run with --commit to copy. Local files are never deleted by this script.")
    return 1 if (missing or skipped) else 0


if __name__ == "__main__":
    raise SystemExit(main())
