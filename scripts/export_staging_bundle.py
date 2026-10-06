"""Build the Render staging bundle from the EXISTING local test data. Run it locally, never on the server.

    python scripts/export_staging_bundle.py

Writes to staging-bundle/ (git-ignored):
    staging_seed.json          the existing registry records (+ certificate files) -> upload as a Render *secret file*
    staging_seed.b64.txt       the same content as one line -> fallback for the STAGING_SEED_B64 env var
    ADMIN_USERNAME.txt         -> Render env var ADMIN_USERNAME
    ADMIN_PASSWORD_HASH.txt    your CURRENT admin password hash -> Render env var ADMIN_PASSWORD_HASH

It only READS a copy of the local database. It does not create, change or reset anything, and it never prints
secrets (only counts and file names). The folder holds secrets and customer-like data: do not commit or share it
publicly; send the files to Render only (and the owner gets the password from you separately).
"""
import _bootstrap  # noqa: F401
import base64
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from app.config import ROOT_DIR, load_settings
from app.services.crypto import CodeVault

OUT = ROOT_DIR / "staging-bundle"
FIELDS = ["registry_number", "dedicated_to", "dedicated_by", "dedication_date", "occasion", "star_catalogue",
          "constellation", "distance", "dedication_message", "status"]


def main() -> int:
    settings = load_settings()
    if not settings.database_path.is_file():
        print(f"No local database at {settings.database_path}.", file=sys.stderr)
        return 1
    vault = CodeVault(settings.secret_key)

    # Read a private copy so the live (possibly running) database is never touched.
    with tempfile.TemporaryDirectory() as tmp:
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(settings.database_path) + suffix)
            if src.exists():
                shutil.copy2(src, Path(tmp) / (settings.database_path.name + suffix))
        conn = sqlite3.connect(Path(tmp) / settings.database_path.name)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM registries ORDER BY id").fetchall()
        cred = conn.execute("SELECT password_hash FROM admin_credentials WHERE username = ?",
                            (settings.admin_username,)).fetchone()
        conn.close()

    records, certs = [], 0
    for row in rows:
        rec = {k: row[k] for k in FIELDS}
        rec["registry_code"] = vault.decrypt(row["registry_code"])
        rec["certificate"] = None
        if row["certificate_path"]:
            path = (settings.upload_dir / row["certificate_path"]).resolve()
            if path.is_file() and path.is_relative_to(settings.upload_dir.resolve()):
                rec["certificate"] = {"filename": path.name, "content_base64": base64.b64encode(path.read_bytes()).decode()}
                certs += 1
            else:
                print(f"WARNING: certificate file for {row['registry_number']} is missing locally; exporting without it.")
        records.append(rec)

    # The hash the owner will use: the one set through the Admin UI if there is one, else the .env value.
    admin_hash = cred["password_hash"] if cred else settings.admin_password_hash
    if not admin_hash.startswith("scrypt:"):
        print("No valid admin password hash found (neither in the database nor in .env).", file=sys.stderr)
        return 1

    seed = json.dumps({"version": 1, "records": records}, indent=2)
    OUT.mkdir(exist_ok=True)
    (OUT / "staging_seed.json").write_text(seed, encoding="utf-8")
    (OUT / "staging_seed.b64.txt").write_text(base64.b64encode(seed.encode()).decode(), encoding="utf-8")
    (OUT / "ADMIN_USERNAME.txt").write_text(settings.admin_username, encoding="utf-8")
    (OUT / "ADMIN_PASSWORD_HASH.txt").write_text(admin_hash, encoding="utf-8")

    by_status = {s: sum(1 for r in records if r["status"] == s) for s in ("active", "inactive")}
    print(f"Exported {len(records)} registry record(s) {by_status} with {certs} certificate file(s).")
    print(f"Admin credential source: {'database (changed in the Admin UI)' if cred else '.env'} - value not shown.")
    print(f"Bundle written to: {OUT}")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
