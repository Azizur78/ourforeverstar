"""Generate ADMIN_PASSWORD_HASH for .env.

    python scripts/hash_password.py            (prompts, input hidden)
"""
import _bootstrap  # noqa: F401
import getpass
import sys

from app.auth.passwords import hash_password


def main() -> int:
    password = getpass.getpass("Admin password: ")
    if len(password) < 10:
        print("Use at least 10 characters.", file=sys.stderr)
        return 1
    if getpass.getpass("Repeat password: ") != password:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    print("\nAdd this line to your .env:\n")
    print(f"ADMIN_PASSWORD_HASH={hash_password(password)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
