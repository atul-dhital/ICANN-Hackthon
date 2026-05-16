"""Tests for the UAReady mail-sending API."""

import os
import sys
import unittest
from contextlib import nullcontext
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uaready.server as server  # noqa: E402
from uaready.sendmail import SmtpConfig  # noqa: E402

app = server.app


class FakeSMTP:
    def __init__(self):
        self.sent = []

    def has_extn(self, name):
        return name.lower() == "smtputf8"

    def send_message(self, message, from_addr=None, to_addrs=None, mail_options=None):
        self.sent.append(
            {
                "message": message,
                "from_addr": from_addr,
                "to_addrs": to_addrs,
                "mail_options": list(mail_options or []),
            }
        )


class TestSendApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_send_uses_sendmail_config_when_smtp_env_is_absent(self):
        fake_smtp = FakeSMTP()
        cfg = SmtpConfig(
            server="smtp.example.test",
            port=465,
            ssl_mode="ssl",
            username="sender@example.com",
            password="secret",
            default_from="sender@example.com",
        )

        with patch.dict(os.environ, {"SMTP_FROM_NAME": "Fallback Sender"}, clear=True), \
                patch("uaready.server.lookup_mx", return_value=[(10, "mx.example.com")]), \
                patch("uaready.server.SmtpConfig.load", return_value=cfg), \
                patch("uaready.server._open_smtp", return_value=nullcontext(fake_smtp)):
            response = self.client.post(
                "/api/send",
                json={
                    "recipient": "ram@example.com",
                    "subject": "Hello",
                    "body": "Test body",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["sender"], "sender@example.com")
        self.assertEqual(fake_smtp.sent[0]["from_addr"], "sender@example.com")

    def test_sends_unicode_recipient_with_smtputf8(self):
        fake_smtp = FakeSMTP()

        with patch("uaready.server.lookup_mx", return_value=[(10, "mx.example.com")]), \
                patch("uaready.server._smtp_settings", return_value={
                    "host": "smtp.example.test",
                    "port": 587,
                    "username": "",
                    "password": "",
                    "use_tls": False,
                    "use_ssl": False,
                    "from_email": "sender@example.com",
                    "from_name": "UAReady Mailer",
                    "timeout": 15,
                }), patch("uaready.server._open_smtp", return_value=nullcontext(fake_smtp)):
            response = self.client.post(
                "/api/send",
                json={
                    "recipient": "राम@example.com",
                    "subject": "Hello",
                    "body": "Test body",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["smtp_utf8_required"])
        self.assertEqual(fake_smtp.sent[0]["mail_options"], ["SMTPUTF8"])

    def test_rejects_invalid_recipient(self):
        with patch("uaready.server._smtp_settings", return_value={
            "host": "smtp.example.test",
            "port": 587,
            "username": "",
            "password": "",
            "use_tls": False,
            "use_ssl": False,
            "from_email": "sender@example.com",
            "from_name": "UAReady Mailer",
            "timeout": 15,
        }):
            response = self.client.post(
                "/api/send",
                json={
                    "recipient": "invalid-address",
                    "subject": "Hello",
                    "body": "Test body",
                },
            )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["ok"])

    def test_rejects_unreachable_recipient_domain(self):
        with patch("uaready.server.lookup_mx", side_effect=RuntimeError("dns failed")), \
                patch("uaready.server.resolve_a", return_value=[]), \
                patch("uaready.server._smtp_settings", return_value={
                    "host": "smtp.example.test",
                    "port": 587,
                    "username": "",
                    "password": "",
                    "use_tls": False,
                    "use_ssl": False,
                    "from_email": "sender@example.com",
                    "from_name": "UAReady Mailer",
                    "timeout": 15,
                }):
            response = self.client.post(
                "/api/send",
                json={
                    "recipient": "user@example.com",
                    "subject": "Hello",
                    "body": "Test body",
                },
            )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertIn(
            "Recipient domain does not resolve to a reachable mail host: example.com",
            data["errors"],
        )

    def test_open_smtp_negotiates_starttls_before_login(self):
        calls = []

        class RecordingSMTP:
            def ehlo(self):
                calls.append("ehlo")

            def starttls(self, context=None):
                calls.append(("starttls", context))

            def login(self, username, password):
                calls.append(("login", username, password))

        fake_client = RecordingSMTP()

        with patch("uaready.server.smtplib.SMTP", return_value=fake_client), \
                patch("uaready.server.ssl.create_default_context", return_value="ctx"):
            client = server._open_smtp(
                {
                    "host": "smtp.example.test",
                    "port": 587,
                    "username": "sender@example.com",
                    "password": "secret",
                    "use_tls": True,
                    "use_ssl": False,
                    "timeout": 15,
                }
            )

        self.assertIs(client, fake_client)
        self.assertEqual(
            calls,
            ["ehlo", ("starttls", "ctx"), "ehlo", ("login", "sender@example.com", "secret")],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
