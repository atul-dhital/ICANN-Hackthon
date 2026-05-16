"""Tests for the UAReady mail-sending API."""

import os
import sys
import unittest
from contextlib import nullcontext
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uaready.server import app  # noqa: E402


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

    def test_sends_unicode_recipient_with_smtputf8(self):
        fake_smtp = FakeSMTP()

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
