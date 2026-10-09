import base64
import json
import sqlite3
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.staging_seed import SeedError
from conftest import ADMIN_PASSWORD, PNG

SEED = {
    "version": 1,
    "records": [
        {"registry_number": "DEV-2026-000001", "registry_code": "SEED-CODE-1", "dedicated_to": "Seed To",
         "dedicated_by": "Seed By", "dedication_date": "2026-02-14", "occasion": "Anniversary",
         "star_catalogue": "HIP 1", "status": "active", "certificate": None},
        {"registry_number": "DEV-2026-000099", "registry_code": "SEED-CODE-99", "dedicated_to": "Cert To",
         "dedicated_by": "Cert By", "dedication_date": "2026-05-01", "status": "inactive",
         "certificate": {"filename": "cert.png", "content_base64": base64.b64encode(PNG).decode()}},
    ],
}


def b64(obj) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()


def verify(c, number, code):
    return c.post("/api/registries/verify", json={"registry_number": number, "registry_code": code})


# ---------------------------------------------------------------- staging seed

def test_seed_restores_existing_records_and_certificate(settings):
    c = TestClient(create_app(replace(settings, staging_seed_b64=b64(SEED))))
    assert verify(c, "DEV-2026-000001", "SEED-CODE-1").status_code == 200      # active, code works
    assert verify(c, "DEV-2026-000099", "SEED-CODE-99").status_code == 404     # inactive stays blocked
    assert verify(c, "DEV-2026-000001", "WRONG-CODE").status_code == 404
    c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    rows = c.get("/api/admin/registries").json()["items"]
    assert sorted(r["registry_number"] for r in rows) == ["DEV-2026-000001", "DEV-2026-000099"]
    cert_row = next(r for r in rows if r["registry_number"] == "DEV-2026-000099")
    assert cert_row["status"] == "inactive" and cert_row["certificate"]["available"]
    assert c.get(f"/api/admin/registries/{cert_row['id']}/certificate").content == PNG


def test_seed_is_idempotent_and_never_overwrites(settings, tmp_path):
    seeded = replace(settings, staging_seed_b64=b64(SEED))
    TestClient(create_app(seeded))
    c = TestClient(create_app(seeded))   # a second boot of the same instance
    c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    items = c.get("/api/admin/registries").json()["items"]
    assert len(items) == 2
    c.put(f"/api/admin/registries/{items[0]['id']}", json={**{k: items[0][k] for k in (
        "registry_number", "registry_code", "dedicated_to", "dedicated_by", "dedication_date")},
        "dedicated_to": "Edited on staging", "status": "active"})
    c2 = TestClient(create_app(seeded))  # restart without a fresh filesystem: the edit survives
    c2.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert "Edited on staging" in [r["dedicated_to"] for r in c2.get("/api/admin/registries").json()["items"]]


def test_fresh_filesystem_gets_the_same_data_again(settings, tmp_path):
    """Simulates a Render restart: new empty database + upload folder, same seed."""
    first = replace(settings, staging_seed_b64=b64(SEED))
    second = replace(first, database_path=tmp_path / "fresh.db", upload_dir=tmp_path / "fresh_uploads")
    for s in (first, second):
        c = TestClient(create_app(s))
        assert verify(c, "DEV-2026-000001", "SEED-CODE-1").status_code == 200
        c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
        assert c.get("/api/admin/stats").json() == {"total": 2, "active": 1, "inactive": 1}


def test_seed_from_secret_file(settings, tmp_path):
    f = tmp_path / "staging_seed.json"
    f.write_text(json.dumps(SEED))
    c = TestClient(create_app(replace(settings, staging_seed_file=f)))
    assert verify(c, "DEV-2026-000001", "SEED-CODE-1").status_code == 200


def test_seed_codes_are_not_stored_in_plaintext(settings):
    TestClient(create_app(replace(settings, staging_seed_b64=b64(SEED))))
    dump = b"".join(p.read_bytes() for p in settings.database_path.parent.glob("test.db*"))
    assert b"SEED-CODE-1" not in dump and b"SEED-CODE-99" not in dump


def test_no_seed_configured_means_no_records(client):
    client.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert client.get("/api/admin/stats").json()["total"] == 0


def test_staging_admin_uses_env_hash_when_database_is_fresh(settings):
    """The credential must come from ADMIN_PASSWORD_HASH on every fresh filesystem."""
    c = TestClient(create_app(replace(settings, staging_seed_b64=b64(SEED))))
    assert c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200
    assert sqlite3.connect(settings.database_path).execute("SELECT COUNT(*) FROM admin_credentials").fetchone()[0] == 0


@pytest.mark.parametrize("seed, expect", [
    ("not json", "not valid JSON"),
    ({"records": "nope"}, '"records" list'),
    ({"records": [5]}, "not an object"),
    ({"records": [{"registry_number": "x", "registry_code": "TOPSECRET-77"}]}, "invalid"),
    ({"records": [{**SEED["records"][0], "certificate": {"filename": "a.exe", "content_base64": "AAAA"}}]}, "invalid certificate"),
])
def test_bad_seed_fails_fast_without_leaking_values(settings, seed, expect):
    raw = seed if isinstance(seed, str) else json.dumps(seed)
    with pytest.raises(SeedError) as err:
        create_app(replace(settings, staging_seed_b64=base64.b64encode(raw.encode()).decode()))
    assert expect in str(err.value) and "TOPSECRET" not in str(err.value)


def test_missing_seed_file_and_bad_base64_fail_clearly(settings, tmp_path):
    with pytest.raises(SeedError, match="does not exist"):
        create_app(replace(settings, staging_seed_file=tmp_path / "missing.json"))
    with pytest.raises(SeedError, match="base64"):
        create_app(replace(settings, staging_seed_b64="***"))


# ---------------------------------------------------------------- single-service hosting

@pytest.fixture()
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>SPA</title>")
    (d / "assets" / "app-abc123.js").write_text("console.log(1)")
    (d / "favicon.svg").write_text("<svg/>")
    (d / "robots.txt").write_text("User-agent: *\nAllow: /")
    (tmp_path / "secret.txt").write_text("TOP-SECRET")
    return d


def test_spa_and_assets_are_served_from_the_same_origin(settings, dist):
    c = TestClient(create_app(replace(settings, frontend_dist=dist)))
    for path in ["/", "/verify", "/registry/abc123", "/admin", "/admin/registries/5/edit", "/nope"]:
        r = c.get(path)
        assert r.status_code == 200 and "SPA" in r.text, path
    assert c.get("/").headers["cache-control"] == "no-cache"
    a = c.get("/assets/app-abc123.js")
    assert a.status_code == 200 and "immutable" in a.headers["cache-control"]
    assert c.get("/favicon.svg").text == "<svg/>"
    assert "Allow: /" in c.get("/robots.txt").text


def test_self_hosted_fonts_are_served_with_font_mime_types(settings, dist):
    (dist / "assets" / "playfair-latin-400-normal-abc123.woff2").write_bytes(b"wOF2" + b"\0" * 16)
    (dist / "assets" / "playfair-latin-400-normal-abc123.woff").write_bytes(b"wOFF" + b"\0" * 16)
    c = TestClient(create_app(replace(settings, frontend_dist=dist)))
    assert c.get("/assets/playfair-latin-400-normal-abc123.woff2").headers["content-type"] == "font/woff2"
    assert c.get("/assets/playfair-latin-400-normal-abc123.woff").headers["content-type"] == "font/woff"


def test_api_still_wins_and_unknown_api_paths_are_json_404(settings, dist):
    c = TestClient(create_app(replace(settings, frontend_dist=dist)))
    assert c.get("/api/health").json() == {"status": "ok"}
    r = c.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json() == {"message": "Not found."}
    assert c.get("/api/admin/stats").status_code == 401   # protection unchanged
    assert c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200


def test_static_serving_blocks_path_traversal(settings, dist):
    c = TestClient(create_app(replace(settings, frontend_dist=dist)))
    for path in ["/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt", "/../secret.txt"]:
        assert "TOP-SECRET" not in c.get(path).text, path


def test_without_frontend_dist_the_api_stays_api_only(client):
    assert client.get("/verify").status_code == 404


def test_missing_dist_index_fails_fast(settings, tmp_path):
    with pytest.raises(RuntimeError, match="npm run build"):
        create_app(replace(settings, frontend_dist=tmp_path / "empty"))


def test_noindex_header_and_robots_for_staging(settings, dist):
    c = TestClient(create_app(replace(settings, frontend_dist=dist, noindex=True)))
    assert c.get("/").headers["x-robots-tag"] == "noindex, nofollow"
    assert c.get("/api/health").headers["x-robots-tag"] == "noindex, nofollow"
    assert "Disallow: /" in c.get("/robots.txt").text
    plain = TestClient(create_app(replace(settings, frontend_dist=dist)))
    assert "x-robots-tag" not in plain.get("/").headers


def test_registry_cookie_works_through_single_service(settings, dist):
    c = TestClient(create_app(replace(settings, frontend_dist=dist, staging_seed_b64=b64(SEED))))
    pid = verify(c, "DEV-2026-000001", "SEED-CODE-1").json()["public_id"]
    assert c.get(f"/api/registries/{pid}").json()["dedicated_to"] == "Seed To"
    assert "SPA" in c.get(f"/registry/{pid}").text   # the page itself is the SPA shell, data only via the API


# ---------------------------------------------------------------- client IP behind a proxy

def test_cloudflare_header_gives_each_visitor_their_own_limit(settings):
    s = replace(settings, trust_proxy=True, client_ip_header="cf-connecting-ip")
    c = TestClient(create_app(s))
    for _ in range(10):
        c.post("/api/registries/verify", json={"registry_number": "X-1234", "registry_code": "WRONG-CODE"},
               headers={"CF-Connecting-IP": "1.1.1.1"})
    blocked = c.post("/api/registries/verify", json={"registry_number": "X-1234", "registry_code": "WRONG-CODE"},
                     headers={"CF-Connecting-IP": "1.1.1.1"})
    other = c.post("/api/registries/verify", json={"registry_number": "X-1234", "registry_code": "WRONG-CODE"},
                   headers={"CF-Connecting-IP": "2.2.2.2"})
    assert blocked.status_code == 429 and other.status_code == 404


def test_spoofed_forwarded_for_prefix_cannot_dodge_the_limit(settings):
    c = TestClient(create_app(replace(settings, trust_proxy=True)))   # default header: x-forwarded-for
    for i in range(10):   # attacker rotates fake leading entries; the proxy appends the real one
        c.post("/api/registries/verify", json={"registry_number": "X-1234", "registry_code": "WRONG-CODE"},
               headers={"X-Forwarded-For": f"9.9.9.{i}, 5.5.5.5"})
    r = c.post("/api/registries/verify", json={"registry_number": "X-1234", "registry_code": "WRONG-CODE"},
               headers={"X-Forwarded-For": "8.8.8.8, 5.5.5.5"})
    assert r.status_code == 429


def test_forwarded_headers_are_ignored_unless_proxy_is_trusted(settings):
    c = TestClient(create_app(settings))   # trust_proxy False
    for i in range(10):
        c.post("/api/registries/verify", json={"registry_number": "X-1234", "registry_code": "WRONG-CODE"},
               headers={"X-Forwarded-For": f"7.7.7.{i}", "CF-Connecting-IP": f"6.6.6.{i}"})
    assert c.post("/api/registries/verify", json={"registry_number": "X-1234", "registry_code": "WRONG-CODE"},
                  headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429
