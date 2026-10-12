import sqlite3

from conftest import PDF, PDF2, PNG


def upload(admin, registry, name, data, ctype="application/octet-stream"):
    return admin.post(f"/api/admin/registries/{registry['id']}/certificate", files={"file": (name, data, ctype)})


def test_valid_pdf_accepted_and_images_are_no_longer_accepted(admin, registry, settings):
    r = upload(admin, registry, "cert.pdf", PDF)
    assert r.status_code == 200
    assert r.json()["certificate"]["available"] is True and r.json()["certificate"]["content_type"] == "application/pdf"
    served = admin.get(f"/api/admin/registries/{registry['id']}/certificate")
    assert served.status_code == 200 and served.content == PDF

    assert upload(admin, registry, "second.pdf", PDF2).json()["certificate"]["content_type"] == "application/pdf"
    for name, data in [("cert.png", PNG), ("cert.jpg", bytes([0xFF, 0xD8, 0xFF]) + bytes(30))]:
        r = upload(admin, registry, name, data)
        assert r.status_code == 415 and "PDF" in r.json()["message"], name


def test_only_path_is_stored_and_replacement_removes_old_file(admin, registry, settings):
    upload(admin, registry, "a.pdf", PDF)
    path1 = sqlite3.connect(settings.database_path).execute("SELECT certificate_path FROM registries").fetchone()[0]
    assert path1.startswith("certificates/") and path1.endswith(".pdf")
    assert (settings.upload_dir / path1).is_file()

    upload(admin, registry, "b.pdf", PDF2)
    assert not (settings.upload_dir / path1).exists()


def test_unsupported_file_type_rejected(admin, registry):
    for name, data in [("x.exe", b"MZ" + b"\x00" * 50), ("x.txt", b"hello"), ("x.svg", b"<svg onload=alert(1)>"),
                       ("x.html", b"<html></html>"), ("noext", PDF)]:
        assert upload(admin, registry, name, data).status_code == 415, name


def test_disguised_file_rejected_by_content_check(admin, registry):
    assert upload(admin, registry, "evil.pdf", b"<html><script>alert(1)</script></html>").status_code == 415
    assert upload(admin, registry, "evil.png", PDF).status_code == 415


def test_empty_file_rejected(admin, registry):
    assert upload(admin, registry, "e.pdf", b"").status_code == 415


def test_oversized_file_rejected(admin, registry):
    big = b"%PDF-" + b"0" * (1024 * 1024 + 10)  # test limit is 1 MB
    r = upload(admin, registry, "big.pdf", big)
    assert r.status_code == 413
    assert "too large" in r.json()["message"].lower()


def test_path_traversal_in_filename_is_harmless(admin, registry, settings):
    r = upload(admin, registry, "../../../evil.pdf", PDF)
    assert r.status_code == 200
    stored = sqlite3.connect(settings.database_path).execute("SELECT certificate_path FROM registries").fetchone()[0]
    assert ".." not in stored and "evil" not in stored


def test_storage_refuses_keys_outside_certificate_dir(settings):
    from app.services.certificates import LocalCertificateStorage
    storage = LocalCertificateStorage(settings.upload_dir)
    secret = settings.upload_dir / "secret.txt"
    secret.write_text("x")
    assert storage.open_path("../secret.txt") is None
    assert storage.open_path("certificates/../secret.txt") is None
    assert storage.open_path(str(secret)) is None


def test_upload_requires_admin(client, registry):
    client.post("/api/admin/logout")
    r = client.post(f"/api/admin/registries/{registry['id']}/certificate", files={"file": ("c.pdf", PDF)})
    assert r.status_code == 401


def test_upload_to_missing_registry_is_404(admin):
    assert admin.post("/api/admin/registries/999/certificate", files={"file": ("c.pdf", PDF)}).status_code == 404
