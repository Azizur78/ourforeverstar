import sqlite3

from fastapi.testclient import TestClient

from app.main import create_app
from conftest import ADMIN_PASSWORD

NEW = "a brand new passphrase 42"


def change(c, current=ADMIN_PASSWORD, new=NEW, confirm=None):
    return c.post("/api/admin/change-password", json={
        "current_password": current, "new_password": new, "confirm_new_password": new if confirm is None else confirm})


def login(c, password):
    return c.post("/api/admin/login", json={"username": "admin", "password": password})


def test_initial_credentials_log_in_and_empty_is_rejected(client):
    assert login(client, ADMIN_PASSWORD).status_code == 200
    fresh = TestClient(create_app(client.app.state.settings))
    assert fresh.post("/api/admin/login", json={"username": "", "password": ""}).status_code == 422
    assert login(fresh, "wrong").status_code == 401
    assert fresh.get("/api/admin/stats").status_code == 401


def test_change_password_requires_authentication(client):
    assert change(client).status_code == 401


def test_successful_change_then_old_fails_and_new_works(admin, settings):
    r = change(admin)
    assert r.status_code == 200 and r.json() == {"message": "Password changed successfully."}
    other = TestClient(create_app(settings))
    assert login(other, ADMIN_PASSWORD).status_code == 401
    assert login(other, NEW).status_code == 200
    assert other.get("/api/admin/stats").status_code == 200


def test_current_session_stays_active_but_other_sessions_end(admin, settings):
    other = TestClient(create_app(settings))
    assert login(other, ADMIN_PASSWORD).status_code == 200
    assert change(admin).status_code == 200
    assert admin.get("/api/admin/stats").status_code == 200       # this session re-issued
    assert other.get("/api/admin/stats").status_code == 401        # older session invalidated


def test_password_is_stored_only_as_a_hash(admin, settings):
    change(admin)
    row = sqlite3.connect(settings.database_path).execute("SELECT username, password_hash FROM admin_credentials").fetchone()
    assert row[0] == "admin" and row[1].startswith("scrypt:")
    assert NEW not in row[1] and ADMIN_PASSWORD not in row[1]
    dump = b"".join(p.read_bytes() for p in settings.database_path.parent.glob("test.db*"))
    assert NEW.encode() not in dump


def test_responses_never_contain_password_or_hash(admin):
    r = change(admin)
    assert NEW not in r.text and "scrypt" not in r.text
    assert "scrypt" not in change(admin, current="nope").text


def test_new_password_survives_restart_and_env_hash_is_no_longer_used(admin, settings):
    change(admin)
    restarted = TestClient(create_app(settings))  # same DB, same env hash
    assert login(restarted, ADMIN_PASSWORD).status_code == 401
    assert login(restarted, NEW).status_code == 200


def test_wrong_current_password_rejected_and_nothing_changes(admin, settings):
    r = change(admin, current="not the password")
    assert r.status_code == 400 and r.json()["message"] == "Current password is incorrect."
    assert r.json()["field"] == "current_password"
    assert login(TestClient(create_app(settings)), ADMIN_PASSWORD).status_code == 200
    assert sqlite3.connect(settings.database_path).execute("SELECT COUNT(*) FROM admin_credentials").fetchone()[0] == 0


def test_mismatched_confirmation_rejected(admin):
    r = change(admin, confirm="something else entirely")
    assert r.status_code == 422 and r.json()["message"] == "New passwords do not match."


def test_weak_passwords_rejected(admin):
    for weak in ["short", "123456789", "          ", "x" * 129]:
        r = change(admin, new=weak)
        assert r.status_code == 422, weak
        assert r.json()["message"] == "Password does not meet the required security requirements."


def test_same_as_current_rejected(admin):
    r = change(admin, new=ADMIN_PASSWORD)
    assert r.status_code == 422 and "different" in r.json()["message"]


def test_empty_fields_rejected(admin):
    assert admin.post("/api/admin/change-password", json={"current_password": "", "new_password": "", "confirm_new_password": ""}).status_code == 422


def test_guessing_current_password_is_rate_limited(admin):
    for _ in range(5):
        assert change(admin, current="guess").status_code == 400
    assert change(admin, current="guess").status_code == 429
    assert change(admin).status_code == 429  # even the right one is held back


def test_logout_still_works_and_blocks_protected_routes(admin):
    assert admin.post("/api/admin/logout").status_code == 200
    for method, path in [("get", "/api/admin/stats"), ("get", "/api/admin/registries"), ("get", "/api/admin/me"),
                         ("post", "/api/admin/change-password")]:
        assert getattr(admin, method)(path).status_code == 401, path


def test_old_session_cookie_cannot_be_replayed_after_change(admin, settings):
    old_cookie = admin.cookies.get("fs_admin_session")
    change(admin)
    replay = TestClient(create_app(settings))
    replay.cookies.set("fs_admin_session", old_cookie, path="/api/admin")
    assert replay.get("/api/admin/stats").status_code == 401


def test_reset_script_can_restore_initial_password(admin, settings, monkeypatch, tmp_path):
    change(admin)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{settings.database_path.as_posix()}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    import sys
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    monkeypatch.setattr(sys, "argv", ["reset_admin_password.py", "--initial"])
    sys.modules.pop("reset_admin_password", None)
    import reset_admin_password
    assert reset_admin_password.main() == 0
    assert sqlite3.connect(settings.database_path).execute("SELECT COUNT(*) FROM admin_credentials").fetchone()[0] == 0


def test_connection_can_be_used_across_threads(settings):
    """FastAPI runs dependencies and handlers on different worker threads; the DB connection must allow that."""
    from concurrent.futures import ThreadPoolExecutor

    from app.database.connection import connect, init_db
    init_db(settings.database_path)
    conn = connect(settings.database_path)
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(lambda: conn.execute("SELECT COUNT(*) FROM registries").fetchone()[0]).result() == 0
    conn.close()
