"""Focused tests for the UAReady mail compose flow."""

import os
import sys
import unittest
from unittest.mock import patch


# allow running directly from the repo root without installing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uaready.server import app  # noqa: E402


class TestMailComposeFlow(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_mail_ui_is_served(self):
        response = self.client.get("/mail/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"UAReady Mail", response.data)

    def test_compose_validation_rejects_bad_link(self):
        with patch("uaready.server.lookup_mx", return_value=[(10, "mx.example.np")]):
            response = self.client.post(
                "/api/compose/validate",
                json={
                    "recipient": "ram@example.np",
                    "subject": "Hello",
                    "body": "Visit https://-invalid-.example for details.",
                },
            )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertTrue(any("Link domain is invalid" in item for item in data["errors"]))

    def test_compose_validation_accepts_valid_message(self):
        with patch("uaready.server.lookup_mx", return_value=[(10, "mx.nepal.nepal")]):
            response = self.client.post(
                "/api/compose/validate",
                json={
                    "recipient": "राम@नेपाल.नेपाल",
                    "subject": "Hello",
                    "body": "Read https://example.com/docs before replying.",
                },
            )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["links"], ["https://example.com/docs"])
        self.assertTrue(data["recipient"]["smtputf8_required"])

    def test_compose_validation_rejects_non_fqdn_recipient_domain(self):
        response = self.client.post(
            "/api/compose/validate",
            json={
                "recipient": "test@example",
                "subject": "Hello",
                "body": "Plain body",
            },
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertIn("Recipient email must use a fully qualified mail domain.", data["errors"])

    def test_compose_validation_rejects_unreachable_mail_domain(self):
        with patch("uaready.server.lookup_mx", side_effect=RuntimeError("dns failed")), \
                patch("uaready.server.resolve_a", return_value=[]):
            response = self.client.post(
                "/api/compose/validate",
                json={
                    "recipient": "user@example.com",
                    "subject": "Hello",
                    "body": "Plain body",
                },
            )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertIn(
            "Recipient domain does not resolve to a reachable mail host: example.com",
            data["errors"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
