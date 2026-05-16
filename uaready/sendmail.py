"""UAReady — SMTPUTF8 live send (stretch goal).

Reads credentials from `uaready/sendmail.ini` (gitignored) or environment
variables, validates the source / destination addresses against the UAReady
validator, then sends a UTF-8 message using the SMTPUTF8 SMTP extension
(RFC 6531). The address envelope is allowed to contain non-ASCII characters
provided the server advertises SMTPUTF8 at EHLO time.

Environment-variable overrides (take precedence over the ini file):

    UAREADY_SMTP_SERVER, UAREADY_SMTP_PORT, UAREADY_SMTP_SSL,
    UAREADY_AUTH_USERNAME, UAREADY_AUTH_PASSWORD, UAREADY_DEFAULT_FROM
"""

from __future__ import annotations

import configparser
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Optional

from .validator import validate_email

HERE = os.path.dirname(os.path.abspath(__file__))
INI_PATH = os.path.join(HERE, "sendmail.ini")


@dataclass
class SmtpConfig:
    server: str
    port: int
    ssl_mode: str           # "ssl" (465), "starttls" (587), or "plain"
    username: str
    password: str
    default_from: str

    @classmethod
    def load(cls, path: str = INI_PATH) -> "SmtpConfig":
        cp = configparser.ConfigParser()
        if os.path.exists(path):
            cp.read(path, encoding="utf-8")
        section = cp["sendmail"] if cp.has_section("sendmail") else {}

        def pick(env_key: str, ini_key: str, default: str = "") -> str:
            return os.environ.get(env_key) or section.get(ini_key, default)

        try:
            cfg = cls(
                server=pick("UAREADY_SMTP_SERVER", "smtp_server"),
                port=int(pick("UAREADY_SMTP_PORT", "smtp_port", "465")),
                ssl_mode=pick("UAREADY_SMTP_SSL", "smtp_ssl", "ssl").lower(),
                username=pick("UAREADY_AUTH_USERNAME", "auth_username"),
                password=pick("UAREADY_AUTH_PASSWORD", "auth_password"),
                default_from=pick("UAREADY_DEFAULT_FROM", "default_from"),
            )
        except KeyError as e:
            raise RuntimeError(
                f"SMTP config missing key {e}. Copy sendmail.ini.example to "
                f"sendmail.ini and fill it in, or set UAREADY_* env vars."
            )
        if not cfg.server or not cfg.username or not cfg.password:
            raise RuntimeError(
                "SMTP config incomplete. Copy uaready/sendmail.ini.example "
                "to uaready/sendmail.ini and fill in server/username/password."
            )
        if not cfg.default_from:
            cfg.default_from = cfg.username
        return cfg


@dataclass
class SendResult:
    ok: bool
    smtputf8_used: bool
    smtputf8_advertised: bool
    message_id: Optional[str] = None
    server_response: Optional[str] = None
    error: Optional[str] = None


def _build_message(sender: str, to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    # message-id needs an ASCII domain — derive from validated sender domain
    sender_res = validate_email(sender)
    id_domain = sender_res.domain_ascii or "uaready.local"
    msg["Message-ID"] = make_msgid(domain=id_domain)
    msg.set_content(body, subtype="plain", charset="utf-8")
    return msg


def send(to: str, subject: str, body: str,
         sender: Optional[str] = None,
         cfg: Optional[SmtpConfig] = None) -> SendResult:
    """Send a UTF-8 email to `to` using SMTPUTF8 if the server supports it.

    Validates both addresses with UAReady's validator before contacting
    the SMTP server, so non-UA-compliant inputs are rejected locally
    rather than producing a confusing 5xx response from Gmail.
    """
    cfg = cfg or SmtpConfig.load()
    sender = sender or cfg.default_from

    s = validate_email(sender)
    if not s.ok:
        return SendResult(False, False, False, error=f"invalid sender: {s.errors}")
    r = validate_email(to)
    if not r.ok:
        return SendResult(False, False, False, error=f"invalid recipient: {r.errors}")

    needs_smtputf8 = s.smtputf8_required or r.smtputf8_required

    msg = _build_message(sender, to, subject, body)

    context = ssl.create_default_context()
    try:
        if cfg.ssl_mode == "ssl":
            client = smtplib.SMTP_SSL(cfg.server, cfg.port, context=context, timeout=15)
        else:
            client = smtplib.SMTP(cfg.server, cfg.port, timeout=15)
        with client:
            client.ehlo()
            if cfg.ssl_mode == "starttls":
                client.starttls(context=context)
                client.ehlo()
            advertised = client.has_extn("smtputf8") or client.has_extn("SMTPUTF8")
            if needs_smtputf8 and not advertised:
                return SendResult(
                    ok=False, smtputf8_used=False, smtputf8_advertised=False,
                    error="server does not advertise SMTPUTF8 but the address "
                          "envelope contains non-ASCII characters",
                )
            client.login(cfg.username, cfg.password)

            mail_options = ["SMTPUTF8"] if advertised and needs_smtputf8 else []
            # send_message handles the envelope split and encodes headers
            # per RFC 6532 when the message is marked utf8 (SMTPUTF8 in
            # mail_options causes smtplib to use the 8BITMIME-style path).
            refused = client.send_message(
                msg, from_addr=sender, to_addrs=[to],
                mail_options=mail_options,
            )
            if refused:
                return SendResult(
                    ok=False, smtputf8_used=bool(mail_options),
                    smtputf8_advertised=advertised,
                    error=f"server refused: {refused}",
                )
        return SendResult(
            ok=True,
            smtputf8_used=bool(mail_options),
            smtputf8_advertised=advertised,
            message_id=msg["Message-ID"],
            server_response="250 accepted",
        )
    except (smtplib.SMTPException, OSError) as e:
        return SendResult(False, False, False, error=f"{type(e).__name__}: {e}")
