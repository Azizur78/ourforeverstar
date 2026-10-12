"""New uploads must be real-looking, complete PDFs within the size limit."""
import io
import sqlite3

import pytest

from app.services.certificates import InvalidCertificate, inspect_stream, validate_certificate
from conftest import PDF, PDF2, PNG, registry_payload

LIMIT = 1024 * 1024
GOOD = b"%PDF-1.7\nbody\n%%EOF\n"


def upload(admin, registry, name, data, kind="certificate"):
    return admin.post(f"/api/admin/registries/{registry['id']}/{kind}", files={"file": (name, data)})


@pytest.mark.parametrize("name", ["a.pdf", "A.PDF", "Mixed.Pdf"])
def test_pdf_extension_is_case_insensitive(admin, registry, name):
    r = upload(admin, registry, name, GOOD)
    assert r.status_code == 200 and r.json()["certificate"]["content_type"] == "application/pdf"


def test_a_truncated_pdf_is_rejected_with_a_helpful_message(admin, registry):
    r = upload(admin, registry, "cut.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\n")      # no end-of-file marker
    assert r.status_code == 415 and "incomplete or damaged" in r.json()["message"]
    assert admin.get(f"/api/admin/registries/{registry['id']}").json()["certificate"]["available"] is False


@pytest.mark.parametrize("name, data", [
    ("photo.png", PNG), ("scan.jpg", bytes([0xFF, 0xD8, 0xFF]) + bytes(40)), ("doc.docx", b"PK\x03\x04" + bytes(40)),
    ("evil.pdf.exe", GOOD), ("noextension", GOOD), ("script.html", b"<html></html>"), ("x.svg", b"<svg/>"),
])
def test_only_pdfs_are_accepted_as_new_uploads(admin, registry, name, data):
    assert upload(admin, registry, name, data).status_code == 415


def test_a_non_pdf_renamed_to_pdf_is_rejected_by_content(admin, registry):
    for data in (PNG + b"%%EOF", b"<html><script>alert(1)</script></html>%%EOF", b"MZ" + bytes(40) + b"%%EOF"):
        r = upload(admin, registry, "renamed.pdf", data)
        assert r.status_code == 415 and "does not match" in r.json()["message"]


def test_size_limit_is_exact(admin, registry):
    fits = b"%PDF-" + b"0" * (LIMIT - 5 - 6) + b"%%EOF\n"
    assert len(fits) == LIMIT
    assert upload(admin, registry, "max.pdf", fits).status_code == 200
    over = upload(admin, registry, "over.pdf", fits + b"0")
    assert over.status_code == 413 and "too large" in over.json()["message"].lower()


def test_empty_file_is_rejected(admin, registry):
    r = upload(admin, registry, "empty.pdf", b"")
    assert r.status_code == 415 and "empty" in r.json()["message"].lower()


def test_both_document_slots_share_the_same_rules(admin, registry):
    assert upload(admin, registry, "r.pdf", GOOD, "registry-document").status_code == 200
    assert upload(admin, registry, "r.png", PNG, "registry-document").status_code == 415
    assert upload(admin, registry, "r.pdf", b"%PDF-1.4 no end", "registry-document").status_code == 415


def test_client_filename_never_decides_the_stored_name(admin, registry, settings):
    upload(admin, registry, "../../../etc/evil name; DROP TABLE.pdf", GOOD)
    key = sqlite3.connect(settings.database_path).execute("SELECT certificate_path FROM registries").fetchone()[0]
    assert key.startswith("certificates/") and key.endswith(".pdf") and "evil" not in key and ".." not in key
    assert len(key) == len("certificates/") + 32 + len(".pdf")


def test_each_upload_gets_its_own_key_so_nothing_is_overwritten(admin, registry, settings):
    other = admin.post("/api/admin/registries", json=registry_payload(registry_number="DEV-2026-000009", registry_code="NINE-CODE-9")).json()
    upload(admin, registry, "a.pdf", PDF)
    upload(admin, other, "same-name.pdf", PDF)
    upload(admin, other, "a.pdf", PDF2)
    keys = [r[0] for r in sqlite3.connect(settings.database_path).execute("SELECT certificate_path FROM registries")]
    assert len(set(keys)) == 2
    assert admin.get(f"/api/admin/registries/{registry['id']}/certificate").content == PDF     # the first registry is untouched


def test_metadata_is_recorded_for_the_admin_overview(admin, registry):
    r = upload(admin, registry, "c.pdf", GOOD).json()["certificate"]
    assert r["size"] == len(GOOD) and r["uploaded_at"].endswith("+00:00")
    assert admin.get(f"/api/admin/registries/{registry['id']}").json()["registry_document"]["size"] is None


def test_inspect_stream_checks_without_consuming_the_stream():
    stream = io.BytesIO(GOOD)
    assert inspect_stream("a.pdf", stream, LIMIT) == (".pdf", len(GOOD))
    assert stream.tell() == 0                                                  # rewound, ready to be stored
    with pytest.raises(InvalidCertificate):
        inspect_stream("a.png", io.BytesIO(PNG), LIMIT)
    assert inspect_stream("old.png", io.BytesIO(PNG), LIMIT, allow_images=True)[0] == ".png"   # only for restoring legacy data


def test_validate_certificate_for_in_memory_data():
    assert validate_certificate("a.pdf", GOOD, LIMIT) == ".pdf"
    with pytest.raises(InvalidCertificate):
        validate_certificate("a.pdf", b"%PDF-1.4 no end marker", LIMIT)
