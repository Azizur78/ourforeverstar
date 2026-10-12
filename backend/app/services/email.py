"""Outgoing email over plain SMTP (standard library only, no paid dependency).

Works with any SMTP relay, including Amazon SES's SMTP interface. Nothing is sent unless SMTP_HOST and EMAIL_FROM are
configured. A successful return means the relay ACCEPTED the message; it is not proof of inbox delivery, and the
application words its status accordingly.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from ..config import Settings
from ..schemas.registry import normalize_email


class EmailNotConfigured(RuntimeError):
    pass


class EmailSender(Protocol):
    def send(self, to: str, subject: str, text: str) -> None: ...


class SmtpEmailSender:
    def __init__(self, host: str, port: int, username: str, password: str, starttls: bool, sender: str):
        self.host, self.port, self.username, self.password = host, port, username, password
        self.starttls, self.sender = starttls, sender

    def send(self, to: str, subject: str, text: str) -> None:
        recipient = normalize_email(to)           # rejects anything containing whitespace or line breaks
        if not recipient or any(ch in subject for ch in "\r\n"):
            raise ValueError("Invalid email header value.")
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)
        context = ssl.create_default_context()
        if self.port == 465:
            client: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=15, context=context)
        else:
            client = smtplib.SMTP(self.host, self.port, timeout=15)
        with client:
            if self.port != 465 and self.starttls:
                client.starttls(context=context)
            if self.username:
                client.login(self.username, self.password)
            refused = client.send_message(message)
        if refused:  # at least one recipient was rejected by the relay
            raise smtplib.SMTPRecipientsRefused(refused)


def build_email_sender(settings: Settings) -> EmailSender | None:
    """None when email is not configured (the admin UI then says so instead of pretending to send)."""
    if not (settings.smtp_host and settings.email_from):
        return None
    return SmtpEmailSender(settings.smtp_host, settings.smtp_port, settings.smtp_username, settings.smtp_password,
                           settings.smtp_starttls, settings.email_from)
