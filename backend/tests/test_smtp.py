"""The real SMTP sender, exercised against a tiny in-process SMTP server (no network, no provider)."""
import smtplib
import socketserver
import threading
from email import message_from_string

import pytest

from app.config import load_settings
from app.services.email import SmtpEmailSender, build_email_sender


class SinkHandler(socketserver.StreamRequestHandler):
    def reply(self, text):
        self.wfile.write(text.encode() + b"\r\n")

    def handle(self):
        self.reply("220 sink ESMTP")
        recipients, sender = [], ""
        while True:
            line = self.rfile.readline().decode(errors="replace").rstrip("\r\n")
            if not line:
                return
            verb = line.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                self.reply("250 sink")
            elif verb == "MAIL":
                sender = line
                self.reply("250 ok")
            elif verb == "RCPT":
                if "reject" in line.lower():
                    self.reply("550 mailbox unavailable")
                else:
                    recipients.append(line)
                    self.reply("250 ok")
            elif verb == "DATA":
                self.reply("354 go ahead")
                body = []
                while True:
                    row = self.rfile.readline().decode(errors="replace")
                    if row in (".\r\n", ".\n", ""):
                        break
                    body.append(row[1:] if row.startswith("..") else row)
                self.server.messages.append({"from": sender, "to": recipients[:], "raw": "".join(body)})
                self.reply("250 queued")
            elif verb == "QUIT":
                self.reply("221 bye")
                return
            else:
                self.reply("250 ok")


@pytest.fixture()
def smtp_sink():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SinkHandler)
    server.daemon_threads = True
    server.messages = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def sender_for(server, **over):
    args = dict(host="127.0.0.1", port=server.server_address[1], username="", password="", starttls=False, sender="Our Forever Star <no-reply@example.test>")
    args.update(over)
    return SmtpEmailSender(**args)


def test_a_message_is_delivered_to_the_relay_with_the_right_headers_and_body(smtp_sink):
    sender_for(smtp_sink).send("Customer@Example.com", "Your registry details", "Registry Number: OFS-1\nRegistry Code: OFS-ABCD\n")
    [sent] = smtp_sink.messages
    assert [r.upper() for r in sent["to"]] == ["RCPT TO:<CUSTOMER@EXAMPLE.COM>"]          # lower-cased, one recipient only
    parsed = message_from_string(sent["raw"])
    assert parsed["Subject"] == "Your registry details" and parsed["To"] == "customer@example.com"
    assert "no-reply@example.test" in parsed["From"]
    assert "OFS-ABCD" in parsed.get_payload()


def test_a_recipient_the_relay_refuses_is_reported_as_a_failure(smtp_sink):
    with pytest.raises(smtplib.SMTPRecipientsRefused):
        sender_for(smtp_sink).send("reject@example.com", "Subject", "body")
    assert smtp_sink.messages == []


def test_an_unreachable_relay_is_a_failure_not_a_silent_success():
    sender = SmtpEmailSender("127.0.0.1", 1, "", "", False, "no-reply@example.test")      # nothing listens on port 1
    with pytest.raises(OSError):
        sender.send("a@example.com", "Subject", "body")


def test_email_is_off_until_it_is_configured(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    for name in ("SMTP_HOST", "EMAIL_FROM"):
        monkeypatch.delenv(name, raising=False)
    assert build_email_sender(load_settings()) is None
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    assert build_email_sender(load_settings()) is None                       # a host alone is not enough
    monkeypatch.setenv("EMAIL_FROM", "no-reply@example.test")
    assert isinstance(build_email_sender(load_settings()), SmtpEmailSender)
