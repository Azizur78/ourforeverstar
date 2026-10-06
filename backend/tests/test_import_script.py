import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

HEADER = "Registry Number,Registry Code,Dedicated To,Dedicated By,Date,Occasion\n"


def run_import(monkeypatch, tmp_path, csv_text, *flags):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'imp.db').as_posix()}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    src = tmp_path / "customers.csv"
    src.write_text(csv_text, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["import_registries.py", str(src), *flags])
    sys.modules.pop("import_registries", None)
    import import_registries
    code = import_registries.main()
    return code, tmp_path / "imp.db"


def count(db):
    return sqlite3.connect(db).execute("SELECT COUNT(*) FROM registries").fetchone()[0] if db.exists() else 0


def test_dry_run_writes_nothing(monkeypatch, tmp_path, capsys):
    code, db = run_import(monkeypatch, tmp_path, HEADER + "HIP-2026-000401,AB12-CD34,A,B,2026-01-05,Birthday\n")
    assert code == 0 and count(db) == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_commit_imports_valid_rows_and_reports_failures(monkeypatch, tmp_path, capsys):
    csv_text = HEADER + (
        "HIP-2026-000401,AB12-CD34,A,B,2026-01-05,Birthday\n"
        "HIP-2026-000402,EF56-GH78,C,D,2026-01-06,\n"
        "HIP-2026-000403,xx,E,F,2026-01-07,\n"            # bad code
        "HIP-2026-000404,JK12-LM34,G,H,05/01/2026,\n"      # date in wrong format
        "HIP-2026-000405,NP12-QR34,,I,2026-01-08,\n"       # missing required name
    )
    code, db = run_import(monkeypatch, tmp_path, csv_text, "--commit")
    out = capsys.readouterr().out
    assert code == 1 and count(db) == 2
    assert "Successfully imported: 2" in out and "Failed: 3" in out and "Duplicates: 0" in out


def test_duplicates_in_file_are_all_refused(monkeypatch, tmp_path, capsys):
    csv_text = HEADER + "HIP-1,AB12-CD34,A,B,2026-01-05,\nHIP-2026-000401,AB12-CD34,A,B,2026-01-05,\nhip-2026-000401,ZZ12-CD34,A,B,2026-01-05,\n"
    code, db = run_import(monkeypatch, tmp_path, csv_text, "--commit")
    out = capsys.readouterr().out
    assert count(db) == 1 and "Duplicates: 2" in out  # only the unique HIP-1 row is written


def test_rerun_detects_existing_records(monkeypatch, tmp_path, capsys):
    row = HEADER + "HIP-2026-000401,AB12-CD34,A,B,2026-01-05,\n"
    run_import(monkeypatch, tmp_path, row, "--commit")
    code, db = run_import(monkeypatch, tmp_path, row, "--commit")
    assert code == 1 and count(db) == 1
    assert "Duplicates: 1" in capsys.readouterr().out


def test_strict_aborts_everything_on_any_problem(monkeypatch, tmp_path):
    csv_text = HEADER + "HIP-2026-000401,AB12-CD34,A,B,2026-01-05,\nHIP-2026-000402,x,C,D,2026-01-05,\n"
    code, db = run_import(monkeypatch, tmp_path, csv_text, "--commit", "--strict")
    assert code == 1 and count(db) == 0


def test_missing_required_column_refused(monkeypatch, tmp_path):
    code, db = run_import(monkeypatch, tmp_path, "Registry Number,Dedicated To\nHIP-2026-000401,A\n", "--commit")
    assert code == 2 and count(db) == 0
