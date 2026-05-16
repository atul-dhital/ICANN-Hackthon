"""Test suite for UAReady — UA Adaptation Hackathon Nepal 2026.

Covers the deliverable requirement: at least 5 valid and 5 invalid
internationalised email and domain inputs.

Run:
    python -m unittest tests.test_uaready -v
"""

import os
import sys
import unittest

# allow running directly from the repo root without installing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uaready import validate_email, validate_domain  # noqa: E402


# --- Valid internationalised inputs ----------------------------------------

VALID_EMAILS = [
    "ram@example.np",                  # Latin / Nepal ccTLD
    "राम@नेपाल.नेपाल",                 # Devanagari local + Devanagari IDN
    "test.user+tag@example.com",       # dot-atom + tag
    "محمد@مثال.السعودية",              # Arabic
    "иван@почта.рф",                   # Cyrillic
    "用户@例子.中国",                  # CJK
]

VALID_DOMAINS = [
    "example.np",
    "नेपाल.नेपाल",                     # Devanagari
    "مثال.السعودية",                   # Arabic
    "почта.рф",                        # Cyrillic
    "例子.中国",                       # CJK
    "xn--11b7c.xn--11b7c",             # already A-label (punycode)
]


# --- Invalid inputs ---------------------------------------------------------

INVALID_EMAILS = [
    "",                                # empty
    "no-at-sign.example",              # missing @
    "double@@example.com",             # multiple @
    "@no-local.com",                   # empty local
    "user@",                           # empty domain
    "..bad@example.com",               # invalid dot position in local
    "user@-invalid-.example",          # bad IDNA label (leading/trailing hyphen)
    "user name@example.com",           # space in local
    "user@exa mple.com",               # space in domain (IDNA rejects)
]

INVALID_DOMAINS = [
    "",                                # empty
    "-leading.example",                # label starts with hyphen
    "trailing-.example",               # label ends with hyphen
    "exa mple.com",                    # space inside
    "a" * 64 + ".com",                 # label > 63 octets
]


# --- Tests ------------------------------------------------------------------

class TestValidEmails(unittest.TestCase):
    def test_all_valid(self):
        for e in VALID_EMAILS:
            with self.subTest(email=e):
                r = validate_email(e)
                self.assertTrue(r.ok, msg=f"{e!r} unexpectedly invalid: {r.errors}")
                self.assertIsNotNone(r.domain_ascii, f"missing A-label for {e!r}")
                self.assertIsNotNone(r.domain_unicode, f"missing U-label for {e!r}")


class TestValidDomains(unittest.TestCase):
    def test_all_valid(self):
        for d in VALID_DOMAINS:
            with self.subTest(domain=d):
                r = validate_domain(d)
                self.assertTrue(r["ok"], msg=f"{d!r} unexpectedly invalid: {r['errors']}")
                self.assertTrue(r["ascii"])


class TestInvalidEmails(unittest.TestCase):
    def test_all_invalid(self):
        for e in INVALID_EMAILS:
            with self.subTest(email=e):
                r = validate_email(e)
                self.assertFalse(r.ok, msg=f"{e!r} unexpectedly valid")
                self.assertTrue(r.errors, msg=f"{e!r} returned no errors")


class TestInvalidDomains(unittest.TestCase):
    def test_all_invalid(self):
        for d in INVALID_DOMAINS:
            with self.subTest(domain=d):
                r = validate_domain(d)
                self.assertFalse(r["ok"], msg=f"{d!r} unexpectedly valid")


class TestStandardsCompliance(unittest.TestCase):
    def test_nfc_normalisation(self):
        # "café" expressed with combining acute accent should be normalised to NFC
        decomposed = "café.com"
        r = validate_domain(decomposed)
        self.assertTrue(r["ok"], r["errors"])
        # decoded form must be the precomposed (NFC) representation
        self.assertEqual(r["unicode"], "café.com")

    def test_idna2008_punycode_roundtrip(self):
        r = validate_domain("नेपाल.नेपाल")
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["ascii"].startswith("xn--"))
        # re-validating the A-label must produce the same U-label
        r2 = validate_domain(r["ascii"])
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["unicode"], r["unicode"])

    def test_smtputf8_flag_on_unicode_local(self):
        r = validate_email("राम@example.com")
        self.assertTrue(r.ok, r.errors)
        self.assertTrue(r.smtputf8_required,
                        "SMTPUTF8 should be required for non-ASCII mailbox")

    def test_smtputf8_flag_off_for_ascii_only(self):
        r = validate_email("ram@example.com")
        self.assertTrue(r.ok)
        self.assertFalse(r.smtputf8_required)

    def test_idn_required_flag(self):
        r = validate_email("ram@नेपाल.नेपाल")
        self.assertTrue(r.ok, r.errors)
        self.assertTrue(r.idn_required)
        self.assertFalse(r.smtputf8_required,
                         "SMTPUTF8 is not required when only the domain is non-ASCII")

    def test_localised_error_nepali(self):
        r = validate_email("no-at-sign.example", lang="ne")
        self.assertFalse(r.ok)
        joined = " ".join(r.errors)
        # Devanagari character present in localised error
        self.assertTrue(any("ऀ" <= ch <= "ॿ" for ch in joined),
                        f"expected Devanagari text in error, got: {r.errors}")

    def test_localised_domain_error_nepali(self):
        r = validate_domain("-invalid-.example", lang="ne")
        self.assertFalse(r["ok"])
        joined = " ".join(r["errors"])
        self.assertTrue(any("ऀ" <= ch <= "ॿ" for ch in joined),
                        f"expected Devanagari text in error, got: {r['errors']}")
        self.assertNotIn("Label must not start or end with a hyphen", joined)

    def test_localised_local_char_error_nepali(self):
        r = validate_email("user name@example.com", lang="ne")
        self.assertFalse(r.ok)
        joined = " ".join(r.errors)
        self.assertTrue(any("ऀ" <= ch <= "ॿ" for ch in joined),
                        f"expected Devanagari text in error, got: {r.errors}")
        self.assertNotIn("before the @-sign", joined)

    def test_label_length_limit(self):
        r = validate_domain(("x" * 63) + ".example.np")
        self.assertTrue(r["ok"], r["errors"])
        r = validate_domain(("x" * 64) + ".example.np")
        self.assertFalse(r["ok"])

    def test_local_octet_length_limit(self):
        # A multi-byte Devanagari character is 3 octets in UTF-8.
        # 22 * 3 = 66 octets — should exceed the 64-octet limit.
        long_local = "क" * 22
        r = validate_email(f"{long_local}@example.np")
        self.assertFalse(r.ok)

    def test_script_detection(self):
        r = validate_email("राम@example.com")
        self.assertIn("Devanagari", r.scripts)
        r = validate_email("ram@example.com")
        self.assertIn("Latin", r.scripts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
