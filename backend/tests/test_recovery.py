"""Manual registry recovery: the public form, the admin review rules and the emails."""
import json
import smtplib
import sqlite3
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routes.recovery import GENERIC_RECEIVED
from app.services.rate_limit import RateLimiter
from conftest import ADMIN_PASSWORD, registry_payload

BASE_URL = "https://stars.example.test"


class FakeSender:
    """Stands in for the SMTP relay. `fail` makes every send raise that exception."""

    def __init__(self, fail=None):
        self.sent, self.fail = [], fail

    def send(self, to, subject, text):
        if self.fail:
            raise self.fail
        self.sent.append({"to": to, "subject": subject, "text": text})


def form(**over):
    data = {"customer_name": "Ann Lee", "email": "ann@example.com", "registry_number": None, "message": None}
    data.update(over)
    return data


def submit(client, **over):
    return client.post("/api/recovery-requests", json=form(**over))


def rows(settings):
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM recovery_requests ORDER BY id")]
    finally:
        conn.close()


@pytest.fixture()
def staff(settings):
    """Admin client on an app with a fake mail relay and a public base URL."""
    c = TestClient(create_app(replace(settings, public_base_url=BASE_URL)))
    assert c.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200
    c.app.state.email_sender = FakeSender()
    return c


@pytest.fixture()
def public(settings):
    return TestClient(create_app(settings))


def make_registry(staff, number="OFS-2026-00035", code="OFS-T3DZ-WFKY", email="ann@example.com", **over):
    r = staff.post("/api/admin/registries", json=registry_payload(registry_number=number, registry_code=code,
                                                                   contact_email=email, **over))
    assert r.status_code == 201, r.text
    return r.json()


def new_request(staff, public, **over):
    assert submit(public, **over).status_code == 202
    return staff.get("/api/admin/recovery").json()["items"][0]


def patch(staff, rid, **body):
    return staff.patch(f"/api/admin/recovery/{rid}", json=body)


def approve_path(staff, rid):
    assert patch(staff, rid, status="under_review").status_code == 200
    return patch(staff, rid, status="approved")


# ------------------------------------------------------------------ the public form

def test_a_submission_is_stored_and_confirmed_generically(public, settings):
    r = submit(public, customer_name="  Ann   Lee ", email=" Ann@Example.COM ", registry_number=" ofs-2026-00035 ",
               message="I lost my card.")
    assert r.status_code == 202 and r.json() == {"message": GENERIC_RECEIVED}
    [row] = rows(settings)
    assert row["status"] == "pending" and row["customer_name"] == "Ann Lee" and row["email"] == "ann@example.com"
    assert row["registry_number"] == "OFS-2026-00035" and row["message"] == "I lost my card."
    assert row["request_ref"].startswith("RR-") and row["created_at"] and row["email_status"] == "not_sent"


def test_the_answer_is_identical_whether_or_not_the_registry_or_email_exist(staff, public):
    make_registry(staff)
    known = submit(public, registry_number="OFS-2026-00035", email="ann@example.com")
    unknown = submit(public, registry_number="NOPE-0000", email="nobody@example.com")
    no_number = submit(public, email="x@y.com")
    assert known.status_code == unknown.status_code == no_number.status_code == 202
    assert known.json() == unknown.json() == no_number.json() == {"message": GENERIC_RECEIVED}
    for text in (known.text, unknown.text):
        assert "OFS-T3DZ-WFKY" not in text and "Test Person" not in text and "ann@example.com" not in text


@pytest.mark.parametrize("bad", [
    {"email": "not an email"}, {"email": "a@b"}, {"email": "x@y.com\r\nBcc: z@y.com"}, {"customer_name": "A"},
    {"customer_name": ""}, {"message": "x" * 1001}, {"registry_number": "X" * 41}, {"email": ""},
])
def test_invalid_submissions_are_rejected_without_storing(public, settings, bad):
    assert submit(public, **bad).status_code == 422
    assert rows(settings) == []


def test_unexpected_fields_cannot_be_smuggled_in(public, settings):
    r = public.post("/api/recovery-requests", json={**form(), "status": "approved", "admin_notes": "x"})
    assert r.status_code == 422 and rows(settings) == []


def test_control_characters_are_stripped(public, settings):
    submit(public, customer_name="Ann" + chr(0) + chr(7) + " Lee", message="line1\nline2" + chr(27))
    [row] = rows(settings)
    assert row["customer_name"] == "Ann Lee" and row["message"] == "line1\nline2"


def test_markup_is_stored_as_inert_text(public, settings, staff):
    submit(public, customer_name="<script>alert(1)</script>", message="<img src=x onerror=alert(1)>")
    detail = staff.get(f"/api/admin/recovery/{staff.get('/api/admin/recovery').json()['items'][0]['id']}").json()
    assert detail["customer_name"] == "<script>alert(1)</script>"       # shown escaped by the UI; never interpreted by the API


def test_a_bot_that_fills_the_honeypot_gets_the_normal_answer_and_nothing_is_stored(public, settings):
    r = submit(public, website="http://spam.example")
    assert r.status_code == 202 and r.json() == {"message": GENERIC_RECEIVED} and rows(settings) == []


def test_duplicate_open_requests_do_not_pile_up(public, settings):
    public.app.state.recovery_limiter = RateLimiter(1000, 3600)        # this test is about duplicates, not the IP limit
    for _ in range(4):
        assert submit(public, registry_number="OFS-1").status_code == 202
    assert len(rows(settings)) == 1
    submit(public, registry_number="OFS-2")                  # a different registry is a different request
    submit(public, email="other@example.com", registry_number="OFS-1")
    assert len(rows(settings)) == 3


def test_one_email_cannot_flood_the_queue(public, settings):
    public.app.state.recovery_limiter = RateLimiter(1000, 3600)
    for n in range(6):
        assert submit(public, registry_number=f"OFS-{n}").status_code == 202
    assert len(rows(settings)) == 3                          # capped per email per day, answer unchanged


def test_a_new_request_is_allowed_once_the_old_one_is_closed(public, settings):
    submit(public, registry_number="OFS-1")
    with sqlite3.connect(settings.database_path) as conn:
        conn.execute("UPDATE recovery_requests SET status = 'rejected'")
    submit(public, registry_number="OFS-1")
    assert len(rows(settings)) == 2


def test_submissions_are_rate_limited_per_visitor(public, settings):
    codes = [submit(public, email=f"user{n}@example.com").status_code for n in range(6)]
    assert codes == [202] * 5 + [429]
    assert len(rows(settings)) == 5


def test_requests_survive_an_application_restart(public, settings):
    submit(public, registry_number="OFS-1")
    restarted = TestClient(create_app(settings))
    restarted.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert restarted.get("/api/admin/recovery").json()["total"] == 1


# ------------------------------------------------------------------ admin access

def test_every_admin_recovery_endpoint_requires_a_login(public):
    for method, path in [("get", "/api/admin/recovery"), ("get", "/api/admin/recovery/summary"), ("get", "/api/admin/recovery/1"),
                         ("patch", "/api/admin/recovery/1"), ("post", "/api/admin/recovery/1/send-email")]:
        assert getattr(public, method)(path).status_code == 401, (method, path)


# ------------------------------------------------------------------ review

def test_list_filter_and_summary(staff, public):
    for n in range(3):
        submit(public, email=f"u{n}@example.com")
    first = staff.get("/api/admin/recovery").json()["items"]
    assert len(first) == 3
    patch(staff, first[0]["id"], status="under_review")
    patch(staff, first[1]["id"], status="rejected")
    assert [i["status"] for i in staff.get("/api/admin/recovery", params={"status": "rejected"}).json()["items"]] == ["rejected"]
    assert staff.get("/api/admin/recovery", params={"status": "bogus"}).status_code == 422
    assert staff.get("/api/admin/recovery/summary").json() == {"pending": 1, "under_review": 1, "approved": 0, "rejected": 1, "completed": 0}


def test_detail_shows_the_submission_and_how_it_compares_with_the_registry(staff, public):
    make_registry(staff)
    cases = {"ann@example.com": "match", "someone.else@example.com": "mismatch"}
    for email, expected in cases.items():
        submit(public, email=email, registry_number="OFS-2026-00035", message="please help")
    items = staff.get("/api/admin/recovery").json()["items"]
    assert {i["email"]: i["registry_match"] for i in items} == cases
    detail = staff.get(f"/api/admin/recovery/{items[0]['id']}").json()
    assert detail["message"] == "please help" and detail["registry"]["registry_number"] == "OFS-2026-00035"
    assert detail["registry"]["contact_email"] == "ann@example.com" and detail["allowed_transitions"] == ["rejected", "under_review"]
    assert detail["email_recipient"] == {"kind": "registry_contact", "masked": "a***@e***.com"}
    assert "OFS-T3DZ-WFKY" not in json.dumps(detail)                  # the registry code is not shown on the request page
    assert staff.get("/api/admin/recovery/9999").status_code == 404


def test_match_states_without_a_registry_or_without_an_email_on_file(staff, public):
    make_registry(staff, number="NOEMAIL-1", code="NOEMAIL-CODE", email=None)
    submit(public, registry_number="NOEMAIL-1")
    submit(public, email="b@example.com")
    submit(public, email="c@example.com", registry_number="DOESNOTEXIST")
    states = {i["email"]: i["registry_match"] for i in staff.get("/api/admin/recovery").json()["items"]}
    assert states == {"ann@example.com": "no_email_on_file", "b@example.com": "no_registry", "c@example.com": "no_registry"}


def test_an_admin_can_link_a_request_to_a_registry_by_number(staff, public):
    make_registry(staff)
    r = new_request(staff, public)
    assert r["registry_match"] == "no_registry"
    assert patch(staff, r["id"], registry_number="DOES-NOT-EXIST").status_code == 422
    linked = patch(staff, r["id"], registry_number="ofs-2026-00035").json()
    assert linked["registry"]["registry_number"] == "OFS-2026-00035" and linked["registry_match"] == "match"


def test_status_changes_record_who_and_when(staff, public):
    r = new_request(staff, public, registry_number="X-1")
    d = patch(staff, r["id"], status="under_review", admin_notes="called Instagram contact").json()
    assert d["status"] == "under_review" and d["reviewed_by"] == "admin" and d["reviewed_at"] and d["admin_notes"] == "called Instagram contact"
    assert d["completed_at"] is None


@pytest.mark.parametrize("start, attempt", [
    ("pending", "approved"), ("pending", "completed"), ("under_review", "completed"), ("rejected", "approved"),
    ("rejected", "completed"), ("completed", "under_review"), ("completed", "rejected"), ("approved", "pending"),
])
def test_invalid_status_transitions_are_refused(staff, public, settings, start, attempt):
    r = new_request(staff, public)
    with sqlite3.connect(settings.database_path) as conn:
        conn.execute("UPDATE recovery_requests SET status = ?", (start,))
    resp = patch(staff, r["id"], status=attempt)
    assert resp.status_code == 409
    assert staff.get(f"/api/admin/recovery/{r['id']}").json()["status"] == start


def test_an_unknown_status_value_is_rejected(staff, public):
    r = new_request(staff, public)
    assert patch(staff, r["id"], status="delete_everything").status_code == 422


# ------------------------------------------------------------------ identity rules

def test_a_matching_name_alone_never_authorises_anything(staff, public):
    make_registry(staff, email="owner@example.com", dedicated_to="Ann Lee")        # same NAME, different email
    r = new_request(staff, public, customer_name="Ann Lee", email="ann@example.com", registry_number="OFS-2026-00035")
    patch(staff, r["id"], status="under_review")
    resp = patch(staff, r["id"], status="approved")
    assert resp.status_code == 422 and "does not match" in resp.json()["message"]
    assert staff.get(f"/api/admin/recovery/{r['id']}").json()["status"] == "under_review"


def test_a_matching_email_lets_the_admin_approve(staff, public):
    make_registry(staff)
    r = new_request(staff, public, email="ANN@example.com", registry_number="OFS-2026-00035")
    d = approve_path(staff, r["id"]).json()
    assert d["status"] == "approved" and d["verification_basis"] == "email_match"


def test_an_email_mismatch_needs_manual_verification_with_a_recorded_note(staff, public):
    registry = make_registry(staff)
    r = new_request(staff, public, email="new.address@example.com", registry_number="OFS-2026-00035")
    patch(staff, r["id"], status="under_review")
    for body in ({"status": "approved"}, {"status": "approved", "manually_verified": True},
                 {"status": "approved", "verification_note": "spoke to them"}):
        assert patch(staff, r["id"], **body).status_code == 422
    ok = patch(staff, r["id"], status="approved", manually_verified=True, verification_note="Matched the Instagram order of 3 March")
    assert ok.status_code == 200 and ok.json()["verification_basis"] == "manual"
    assert "Manual verification by admin" in ok.json()["admin_notes"] and "Instagram order of 3 March" in ok.json()["admin_notes"]
    assert staff.get(f"/api/admin/registries/{registry['id']}").json()["contact_email"] == "ann@example.com"   # never rewritten


def test_a_registry_with_no_email_on_file_also_needs_manual_verification(staff, public):
    make_registry(staff, email=None)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    patch(staff, r["id"], status="under_review")
    refused = patch(staff, r["id"], status="approved")
    assert refused.status_code == 422 and "no contact email" in refused.json()["message"]
    assert patch(staff, r["id"], status="approved", manually_verified=True, verification_note="verified by phone").status_code == 200


def test_approval_needs_a_linked_registry(staff, public):
    r = new_request(staff, public)
    patch(staff, r["id"], status="under_review")
    resp = patch(staff, r["id"], status="approved", manually_verified=True, verification_note="x")
    assert resp.status_code == 422 and "Link this request" in resp.json()["message"]


def test_reopening_a_request_requires_verification_again(staff, public):
    make_registry(staff)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    approve_path(staff, r["id"])
    reopened = patch(staff, r["id"], status="under_review").json()
    assert reopened["verification_basis"] is None
    assert patch(staff, r["id"], status="approved").json()["verification_basis"] == "email_match"


def test_the_linked_registry_cannot_be_swapped_after_approval(staff, public):
    make_registry(staff)
    make_registry(staff, number="OFS-2026-00036", code="OFS-OTHER-1")
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    approve_path(staff, r["id"])
    assert patch(staff, r["id"], registry_number="OFS-2026-00036").status_code == 409


def test_notes_are_private_to_admins(staff, public):
    r = new_request(staff, public)
    patch(staff, r["id"], admin_notes="PRIVATE-NOTE")
    assert "PRIVATE-NOTE" not in submit(public, email="z@example.com").text
    assert "PRIVATE-NOTE" in staff.get(f"/api/admin/recovery/{r['id']}").text


# ------------------------------------------------------------------ email

def test_only_an_approved_request_can_be_emailed(staff, public):
    make_registry(staff)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    assert staff.post(f"/api/admin/recovery/{r['id']}/send-email").status_code == 409          # pending
    patch(staff, r["id"], status="under_review")
    assert staff.post(f"/api/admin/recovery/{r['id']}/send-email").status_code == 409          # under review
    assert staff.app.state.email_sender.sent == []


def test_a_rejected_request_never_sends_details(staff, public):
    make_registry(staff)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    patch(staff, r["id"], status="rejected")
    assert staff.post(f"/api/admin/recovery/{r['id']}/send-email").status_code == 409
    assert staff.app.state.email_sender.sent == []
    assert "OFS-T3DZ-WFKY" not in staff.get(f"/api/admin/recovery/{r['id']}").text


def test_details_go_to_the_registrys_own_email_with_the_number_and_code_and_a_link(staff, public):
    make_registry(staff)
    r = new_request(staff, public, customer_name="Ann Lee", email="ann@example.com", registry_number="OFS-2026-00035")
    approve_path(staff, r["id"])
    out = staff.post(f"/api/admin/recovery/{r['id']}/send-email")
    assert out.status_code == 200
    [mail] = staff.app.state.email_sender.sent
    assert mail["to"] == "ann@example.com" and mail["subject"] == "Your Our Forever Star registry details"
    assert "OFS-2026-00035" in mail["text"] and "OFS-T3DZ-WFKY" in mail["text"] and f"{BASE_URL}/verify" in mail["text"]
    assert "Hello Ann Lee" in mail["text"]
    for forbidden in ("X-Amz", "amazonaws", ".pdf", "certificates/", "?download"):
        assert forbidden not in mail["text"], forbidden
    assert mail["text"].count("http") == 1                                   # the only link is the site's own verify page


def test_a_successful_send_completes_the_request_and_records_it(staff, public):
    make_registry(staff)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    approve_path(staff, r["id"])
    d = staff.post(f"/api/admin/recovery/{r['id']}/send-email").json()
    assert d["email_status"] == "sent" and d["email_sent_at"] and d["email_error"] is None
    assert d["status"] == "completed" and d["completed_at"] and "accepted the email" in d["notice"]
    assert staff.post(f"/api/admin/recovery/{r['id']}/send-email").status_code == 409      # cannot be sent twice


def test_details_are_never_sent_to_an_unverified_submitted_address(staff, public):
    make_registry(staff, email="owner@example.com")
    r = new_request(staff, public, email="stranger@example.com", registry_number="OFS-2026-00035")
    patch(staff, r["id"], status="under_review")
    patch(staff, r["id"], status="approved", manually_verified=True, verification_note="verified the order by chat")
    staff.post(f"/api/admin/recovery/{r['id']}/send-email")
    [mail] = staff.app.state.email_sender.sent
    assert mail["to"] == "owner@example.com"                                   # the registry's own address, not the form's
    assert all(m["to"] != "stranger@example.com" for m in staff.app.state.email_sender.sent)


def test_the_submitted_address_is_used_only_after_manual_verification_when_the_registry_has_none(staff, public):
    make_registry(staff, email=None)
    r = new_request(staff, public, email="customer@example.com", registry_number="OFS-2026-00035")
    patch(staff, r["id"], status="under_review")
    patch(staff, r["id"], status="approved", manually_verified=True, verification_note="confirmed through the order chat")
    d = staff.get(f"/api/admin/recovery/{r['id']}").json()
    assert d["email_recipient"]["kind"] == "submitted_after_manual_verification"
    staff.post(f"/api/admin/recovery/{r['id']}/send-email")
    assert staff.app.state.email_sender.sent[0]["to"] == "customer@example.com"


def test_an_email_failure_is_recorded_and_the_request_is_not_marked_completed(staff, public):
    make_registry(staff)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    approve_path(staff, r["id"])
    staff.app.state.email_sender = FakeSender(fail=smtplib.SMTPAuthenticationError(535, b"password=hunter2 rejected"))
    resp = staff.post(f"/api/admin/recovery/{r['id']}/send-email")
    assert resp.status_code == 502 and "hunter2" not in resp.text and "stays Approved" in resp.json()["message"]
    d = staff.get(f"/api/admin/recovery/{r['id']}").json()
    assert d["status"] == "approved" and d["email_status"] == "failed" and d["email_error"] == "SMTPAuthenticationError"
    assert d["email_sent_at"] is None and d["completed_at"] is None and "hunter2" not in json.dumps(d)
    staff.app.state.email_sender = FakeSender()                                # fixed: retry works
    again = staff.post(f"/api/admin/recovery/{r['id']}/send-email").json()
    assert again["status"] == "completed" and again["email_status"] == "sent" and again["email_error"] is None


def test_unconfigured_email_says_so_and_changes_nothing(staff, public):
    make_registry(staff)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    approve_path(staff, r["id"])
    staff.app.state.email_sender = None
    resp = staff.post(f"/api/admin/recovery/{r['id']}/send-email")
    assert resp.status_code == 503 and "not configured" in resp.json()["message"]
    d = staff.get(f"/api/admin/recovery/{r['id']}").json()
    assert d["status"] == "approved" and d["email_status"] == "not_sent"


def test_an_admin_can_close_a_request_without_email(staff, public):
    make_registry(staff)
    r = new_request(staff, public, registry_number="OFS-2026-00035")
    approve_path(staff, r["id"])
    d = patch(staff, r["id"], status="completed", admin_notes="Resolved on Instagram").json()
    assert d["status"] == "completed" and d["completed_at"] and d["email_status"] == "not_sent"


def test_email_headers_cannot_be_injected(public):
    from app.services.email import SmtpEmailSender
    sender = SmtpEmailSender("localhost", 25, "", "", False, "from@example.com")
    for bad in ("a@b.com\r\nBcc: x@y.com", "a b@c.com", "no-at-sign"):
        with pytest.raises(ValueError):
            sender.send(bad, "Subject", "body")
    with pytest.raises(ValueError):
        sender.send("a@b.com", "Subject\r\nBcc: x@y.com", "body")


# ------------------------------------------------------------------ the private contact email on a registry

def test_contact_email_is_validated_lowercased_and_admin_only(staff, public):
    r = staff.post("/api/admin/registries", json=registry_payload(contact_email="  Owner@Example.COM "))
    assert r.status_code == 201 and r.json()["contact_email"] == "owner@example.com"
    for bad in ("nope", "a@b", "a b@c.com"):
        assert staff.post("/api/admin/registries", json=registry_payload(registry_number="BAD-0001", contact_email=bad)).status_code == 422
    assert staff.post("/api/admin/registries", json=registry_payload(registry_number="BLANK-001", registry_code="BLANK-CODE", contact_email="  ")).json()["contact_email"] is None
    c = TestClient(staff.app)
    pid = c.post("/api/registries/verify", json={"registry_number": "DEV-2026-000001", "registry_code": "TEST-CODE-1"}).json()["public_id"]
    assert "owner@example.com" not in c.get(f"/api/registries/{pid}").text and '"contact_email"' not in c.get(f"/api/registries/{pid}").text


def test_contact_email_can_be_set_by_batch_and_edit(staff):
    records = [registry_payload(registry_number=f"B-{i}", registry_code=f"BCODE-{i}", contact_email=f"c{i}@example.com") for i in (1, 2)]
    out = staff.post("/api/admin/registries/batch", data={"records": json.dumps(records), "certificate_indexes": "[]"})
    assert out.status_code == 201 and sorted(c["contact_email"] for c in out.json()["created"]) == ["c1@example.com", "c2@example.com"]
    item = out.json()["created"][0]
    edit = staff.put(f"/api/admin/registries/{item['id']}", json=registry_payload(registry_number=item["registry_number"], registry_code="BCODE-1" if item["registry_number"] == "B-1" else "BCODE-2", contact_email=None))
    assert edit.status_code == 200 and edit.json()["contact_email"] is None
