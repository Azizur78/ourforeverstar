"""Emergency admin password reset (run by the developer on the server).

    python scripts/reset_admin_password.py           # set a new password (prompts, input hidden)
    python scripts/reset_admin_password.py --initial # forget the UI-set password; ADMIN_PASSWORD_HASH from .env applies again
"""
import _bootstrap  # noqa: F401
import getpass
import sys

from app.auth.passwords import hash_password
from app.config import load_settings
from app.database.admin_repository import AdminCredentialStore
from app.database.connection import connect, init_db


def main() -> int:
    settings = load_settings()
    init_db(settings.database_path)
    conn = connect(settings.database_path)
    try:
        if "--initial" in sys.argv:
            conn.execute("DELETE FROM admin_credentials WHERE username = ?", (settings.admin_username,))
            conn.commit()
            print("UI-set password removed. The ADMIN_PASSWORD_HASH from .env is active again.")
            return 0
        password = getpass.getpass("New admin password: ")
        if not 10 <= len(password) <= 128 or not password.strip():
            print("Use 10 to 128 characters.", file=sys.stderr)
            return 1
        if getpass.getpass("Repeat password: ") != password:
            print("Passwords do not match.", file=sys.stderr)
            return 1
        AdminCredentialStore(conn, settings).set_hash(hash_password(password))
        print("Admin password updated. All existing admin sessions are now signed out.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
