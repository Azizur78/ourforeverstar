import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app
from conftest import ADMIN_PASSWORD, PDF, PDF2, registry_payload


def rec(n, **kw):
    """A valid record; n makes the registry number and code unique."""
    data = registry_payload(registry_number=f"BATCH-2026-{n:06d}", registry_code=f"BATCH-CODE-{n}",
                            dedicated_to=f"To {n}", dedicated_by=f"By {n}")
    data.update(kw)
    return data


def post(client, records, certs=None):
    """certs: {record_index: (filename, bytes)}"""
    certs = certs or {}
    files = [("certificates", (name, data)) for _, (name, data) in certs.items()]
    return client.post("/api/admin/registries/batch", files=files or None, data={
        "records": json.dumps(records), "certificate_indexes": json.dumps(list(certs.keys()))})


def count(settings):
    return sqlite3.connect(settings.database_path).execute("SELECT COUNT(*) FROM registries").fetchone()[0]


def cert_files(settings):
    d = settings.upload_dir / "certificates"
    return sorted(p.name for p in d.glob("*")) if d.exists() else []


def numbers(admin):
    return sorted(r["registry_number"] for r in admin.get("/api/admin/registries", params={"page_size": 100}).json()["items"])


# ---------------------------------------------------------------- creating

def test_single_record_batch(admin, settings):
    r = post(admin, [rec(1)])
    assert r.status_code == 201 and r.json()["count"] == 1
    assert r.json()["created"][0]["registry_code"] == "BATCH-CODE-1"
    assert count(settings) == 1


def test_two_and_three_records_in_one_request(admin, settings):
    assert post(admin, [rec(1), rec(2)]).json()["count"] == 2
    r = post(admin, [rec(3), rec(4), rec(5)])
    assert r.status_code == 201 and r.json()["count"] == 3
    assert numbers(admin) == [f"BATCH-2026-{i:06d}" for i in range(1, 6)]


def test_created_records_work_end_to_end(admin, settings):
    post(admin, [rec(1), rec(2, status="inactive")])
    customer = TestClient(create_app(settings))
    assert customer.post("/api/registries/verify", json={
        "registry_number": "BATCH-2026-000001", "registry_code": "BATCH-CODE-1"}).status_code == 200
    assert customer.post("/api/registries/verify", json={
        "registry_number": "BATCH-2026-000002", "registry_code": "BATCH-CODE-2"}).status_code == 404  # inactive
    assert admin.get("/api/admin/stats").json() == {"total": 2, "active": 1, "inactive": 1}


def test_codes_are_hashed_and_encrypted_like_single_create(admin, settings):
    post(admin, [rec(1)])
    row = sqlite3.connect(settings.database_path).execute("SELECT registry_code, registry_code_hash FROM registries").fetchone()
    assert "BATCH-CODE-1" not in row[0] and "BATCH-CODE-1" not in row[1]


def test_blank_optional_fields_and_normalization(admin):
    r = post(admin, [rec(1, occasion="  ", star_catalogue="", registry_number="batch-2026-000001")])
    created = r.json()["created"][0]
    assert r.status_code == 201 and created["occasion"] is None and created["registry_number"] == "BATCH-2026-000001"


# ---------------------------------------------------------------- all or nothing

def test_empty_required_field_rejects_whole_batch(admin, settings):
    r = post(admin, [rec(1), rec(2, dedicated_to=""), rec(3)])
    assert r.status_code == 422
    assert r.json()["message"] == "1 record needs attention. Nothing was saved."
    assert r.json()["errors"] == [{"index": 1, "field": "dedicated_to", "message": r.json()["errors"][0]["message"]}]
    assert count(settings) == 0


def test_duplicate_inside_batch_is_rejected_and_identifies_both_records(admin, settings):
    r = post(admin, [rec(1), rec(2, registry_number="BATCH-2026-000001"), rec(3)])
    assert r.status_code == 422
    errs = [(e["index"], e["field"], e["message"]) for e in r.json()["errors"]]
    assert errs == [(0, "registry_number", "Duplicate registry number in this batch."),
                    (1, "registry_number", "Duplicate registry number in this batch.")]
    assert count(settings) == 0


def test_duplicate_inside_batch_ignores_case(admin, settings):
    r = post(admin, [rec(1), rec(2, registry_number="batch-2026-000001")])
    assert r.status_code == 422 and count(settings) == 0


def test_existing_registry_number_is_protected_and_nothing_else_is_saved(admin, settings):
    admin.post("/api/admin/registries", json=rec(1))
    before = admin.get("/api/admin/registries").json()["items"][0]
    r = post(admin, [rec(2), rec(3, registry_number="BATCH-2026-000001", dedicated_to="Overwrite attempt"), rec(4)])
    assert r.status_code == 422
    assert r.json()["errors"] == [{"index": 1, "field": "registry_number", "message": "Registry number already exists."}]
    assert count(settings) == 1                                   # records 2 and 4 were NOT saved
    after = admin.get("/api/admin/registries").json()["items"][0]
    assert after == before                                        # the existing registry is untouched


def test_all_problems_are_reported_together(admin, settings):
    r = post(admin, [rec(1, registry_number="x"), rec(2), rec(3, registry_code="no"), rec(4, registry_number="BATCH-2026-000002")])
    assert r.status_code == 422
    # index 0 bad number, 2 bad code, 1 and 3 share a registry number (both are flagged)
    assert r.json()["message"] == "4 records need attention. Nothing was saved."
    assert sorted({e["index"] for e in r.json()["errors"]}) == [0, 1, 2, 3]
    assert count(settings) == 0


def test_errors_do_not_leak_codes_or_internals(admin):
    r = post(admin, [rec(1, registry_code="SECRET-CODE-XYZ", registry_number="x")])
    assert "SECRET-CODE-XYZ" not in r.text and "Traceback" not in r.text and "sqlite" not in r.text.lower()


def test_empty_malformed_and_oversized_batches(admin, settings):
    assert post(admin, []).status_code == 422
    assert admin.post("/api/admin/registries/batch", data={"records": "not json"}).status_code == 422
    assert admin.post("/api/admin/registries/batch", data={"records": json.dumps({"a": 1})}).status_code == 422
    assert admin.post("/api/admin/registries/batch", data={"records": json.dumps(["x"])}).status_code == 422
    assert post(admin, [rec(i) for i in range(1, 52)]).status_code == 422          # more than 50
    assert post(admin, [{**rec(1), "id": 7}]).status_code == 422                    # unknown field
    assert count(settings) == 0


def test_requires_admin(client):
    assert post(client, [rec(1)]).status_code == 401


# ---------------------------------------------------------------- double submit

def test_submitting_the_same_batch_twice_creates_no_duplicates(admin, settings):
    assert post(admin, [rec(1), rec(2)]).status_code == 201
    again = post(admin, [rec(1), rec(2)])
    assert again.status_code == 422 and count(settings) == 2


def test_truly_concurrent_identical_batches_create_exactly_one_set(settings):
    clients = []
    for _ in range(2):
        c = TestClient(create_app(settings))
        c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
        clients.append(c)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda c: post(c, [rec(1), rec(2), rec(3)]).status_code, clients))
    assert results.count(201) == 1 and all(s in (201, 409, 422) for s in results)
    assert count(settings) == 3


# ---------------------------------------------------------------- certificates

def test_each_record_keeps_its_own_certificate(admin, settings):
    r = post(admin, [rec(1), rec(2), rec(3)], certs={0: ("one.pdf", PDF), 2: ("three.pdf", PDF2)})
    assert r.status_code == 201
    created = {c["registry_number"]: c for c in r.json()["created"]}
    one, two, three = (created[f"BATCH-2026-{i:06d}"] for i in (1, 2, 3))
    assert one["certificate"]["available"] is True and one["certificate"]["content_type"] == "application/pdf"
    assert two["certificate"]["available"] is False and two["certificate"]["content_type"] is None      # did not inherit record 1's file
    assert three["certificate"]["content_type"] == "application/pdf" and three["certificate"]["available"]
    assert admin.get(f"/api/admin/registries/{one['id']}/certificate").content == PDF
    assert admin.get(f"/api/admin/registries/{three['id']}/certificate").content == PDF2
    assert admin.get(f"/api/admin/registries/{two['id']}/certificate").status_code == 404
    assert len(cert_files(settings)) == 2


def test_bad_certificate_rejects_whole_batch_and_leaves_no_files(admin, settings):
    r = post(admin, [rec(1), rec(2)], certs={0: ("ok.pdf", PDF), 1: ("evil.exe", b"MZ" + b"\0" * 20)})
    assert r.status_code == 422
    assert r.json()["errors"][0]["index"] == 1 and r.json()["errors"][0]["field"] == "certificate"
    assert count(settings) == 0 and cert_files(settings) == []


def test_disguised_oversized_and_empty_certificates_rejected(admin, settings):
    big = b"%PDF-" + b"0" * (1024 * 1024 + 10)   # test limit is 1 MB
    for name, data in [("x.pdf", b"<html>"), ("big.pdf", big), ("empty.pdf", b"")]:
        r = post(admin, [rec(1)], certs={0: (name, data)})
        assert r.status_code == 422 and r.json()["errors"][0]["field"] == "certificate", name
    assert count(settings) == 0 and cert_files(settings) == []


def test_certificate_errors_and_record_errors_are_reported_together(admin, settings):
    r = post(admin, [rec(1, dedicated_by=""), rec(2)], certs={1: ("bad.txt", b"hello")})
    assert sorted((e["index"], e["field"]) for e in r.json()["errors"]) == [(0, "dedicated_by"), (1, "certificate")]
    assert cert_files(settings) == []


def test_certificate_index_mismatch_is_rejected(admin, settings):
    for indexes in ([5], [0, 0], ["a"], []):
        r = admin.post("/api/admin/registries/batch", files=[("certificates", ("c.pdf", PDF))],
                       data={"records": json.dumps([rec(1)]), "certificate_indexes": json.dumps(indexes)})
        assert r.status_code == 422, indexes
    assert count(settings) == 0 and cert_files(settings) == []


def test_database_failure_cleans_up_saved_certificates(admin, settings, monkeypatch):
    from app.database import registry_repository as rr

    def boom(self, rows):
        raise RuntimeError("disk full")
    monkeypatch.setattr(rr.RegistryRepository, "create_many", boom)
    c = TestClient(create_app(settings), raise_server_exceptions=False)
    c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    r = post(c, [rec(1)], certs={0: ("one.pdf", PDF)})
    assert r.status_code == 500 and "disk full" not in r.text and "Traceback" not in r.text
    assert cert_files(settings) == [] and count(settings) == 0


# ---------------------------------------------------------------- existing behaviour unchanged

def test_single_create_endpoint_still_works_and_shares_the_same_rules(admin):
    assert admin.post("/api/admin/registries", json=rec(1)).status_code == 201
    assert admin.post("/api/admin/registries", json=rec(1)).status_code == 409
    assert post(admin, [rec(1)]).status_code == 422
