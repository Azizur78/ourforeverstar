"""Insert clearly-marked DEVELOPMENT records for local testing only.

    python scripts/seed_dev.py

Records use the DEV- prefix and fictional names. They are not real customers.
Refuses to run when APP_ENV=production.
"""
import _bootstrap  # noqa: F401
from datetime import date

from app.config import load_settings
from app.database.connection import connect, init_db
from app.database.registry_repository import RegistryRepository
from app.schemas.registry import RegistryWrite
from app.services.crypto import CodeVault
from app.services.registry_service import to_storage

DEV_RECORDS = [
    dict(registry_number="DEV-2026-000001", registry_code="DEMO-CODE-0001",
         dedicated_to="Sample Person A", dedicated_by="Sample Person B", dedication_date=date(2026, 2, 14),
         occasion="Anniversary", star_catalogue="HIP 00000 (dev)", constellation="Vulpecula (dev)",
         distance="Sample distance (dev)",
         dedication_message="DEVELOPMENT RECORD - sample dedication text for local testing only."),
    dict(registry_number="DEV-2026-000002", registry_code="DEMO-CODE-0002",
         dedicated_to="Sample Person C", dedicated_by="Sample Person D", dedication_date=date(2026, 3, 1),
         occasion="Birthday", star_catalogue="HIP 00001 (dev)", constellation="Lyra (dev)",
         distance="Sample distance (dev)",
         dedication_message="DEVELOPMENT RECORD - second sample for testing."),
    dict(registry_number="DEV-2026-000003", registry_code="DEMO-CODE-0003",
         dedicated_to="Sample Person E", dedicated_by="Sample Person F", dedication_date=date(2026, 4, 9),
         occasion="Memorial", dedication_message="DEVELOPMENT RECORD - inactive sample.", status="inactive"),
]


def main() -> int:
    settings = load_settings()
    if settings.is_production:
        print("Refusing to seed development data when APP_ENV=production.")
        return 1
    init_db(settings.database_path)
    vault = CodeVault(settings.secret_key)
    conn = connect(settings.database_path)
    repo = RegistryRepository(conn)
    added = 0
    for record in DEV_RECORDS:
        if repo.get_by_number(record["registry_number"]):
            continue
        repo.create(to_storage(RegistryWrite(**record), vault))
        added += 1
    conn.close()
    print(f"Added {added} development record(s). Verify with e.g. DEV-2026-000001 / DEMO-CODE-0001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
