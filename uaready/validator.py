"""UAReady — internationalised email & domain validation.

Standards implemented:
  - RFC 6531  (SMTPUTF8)             internationalised SMTP extension
  - RFC 6532  (EAI)                  internationalised email headers
  - RFC 5321  (SMTP)                 length & syntax limits
  - RFC 5891 / IDNA2008              international domain names
  - UTS #46                          unicode IDNA compatibility mapping
  - UTS #39  (mixed-script policy)   homograph-risk warning
  - Unicode NFC                      normalisation for stable comparison

Engines:
  - `email-validator`  primary RFC 6531/6532 engine for email
  - `idna`             IDNA2008 / UTS#46 engine for the domain-only API
  - `pyIsEmail`        optional per-RFC diagnosis codes (--diagnose)

This module is a thin localising wrapper around the engines: it handles
NFC normalisation, multi-script detection, localised error messages
(en / ne / hi / ar), a UTS #39 inspired mixed-script warning in the local
part, and a stable ValidationResult API.
"""

import unicodedata
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import idna
from email_validator import (
    validate_email as _ev_validate,
    EmailNotValidError,
)

try:
    from pyisemail import is_email as _pyis_is_email
    _PYIS_AVAILABLE = True
except ImportError:
    _PYIS_AVAILABLE = False

from .errors import msg, DEFAULT_LANG


MAX_LOCAL_OCTETS = 64
MAX_EMAIL_OCTETS = 254
MAX_DOMAIN_OCTETS = 253
MAX_LABEL_OCTETS = 63


@dataclass
class ValidationResult:
    ok: bool
    input: str
    normalized: Optional[str] = None
    local: Optional[str] = None
    domain_unicode: Optional[str] = None
    domain_ascii: Optional[str] = None
    smtputf8_required: bool = False
    idn_required: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    scripts: List[str] = field(default_factory=list)
    diagnosis: Optional[dict] = None

    def to_dict(self):
        return asdict(self)


# ---- helpers ---------------------------------------------------------------

# Map Unicode-name keywords to script labels we surface to the user.
_SCRIPT_NAME_MAP = (
    ("DEVANAGARI", "Devanagari"),
    ("ARABIC",     "Arabic"),
    ("CYRILLIC",   "Cyrillic"),
    ("TAMIL",      "Tamil"),
    ("BENGALI",    "Bengali"),
    ("GREEK",      "Greek"),
    ("HEBREW",     "Hebrew"),
    ("HIRAGANA",   "CJK"),
    ("KATAKANA",   "CJK"),
    ("HANGUL",     "CJK"),
    ("CJK",        "CJK"),
)


def _detect_scripts(s: str) -> List[str]:
    """Return the sorted set of Unicode scripts present in *s*.

    Punctuation, digits, '@' and '.' are ignored — only letters count.
    Used both as informational output and as the input to the UTS #39
    inspired mixed-script policy.
    """
    seen = set()
    for ch in s:
        if ch in "@.":
            continue
        if ch.isascii():
            if ch.isalpha():
                seen.add("Latin")
            continue
        try:
            name = unicodedata.name(ch, "")
        except ValueError:
            continue
        for needle, label in _SCRIPT_NAME_MAP:
            if needle in name:
                seen.add(label)
                break
        else:
            seen.add("Other")
    return sorted(seen)


def _has_control(s: str) -> bool:
    return any(unicodedata.category(c).startswith("C") for c in s)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _map_domain_error(detail: str, lang: str) -> str:
    """Map IDNA/domain-format engine text to a localised UAReady message."""
    text = detail.lower()
    if "too long" in text and "label" in text:
        return msg("label_too_long", lang)
    if "too long" in text:
        return msg("domain_too_long", lang)
    if "start or end with a hyphen" in text:
        return msg("label_hyphen_position", lang)
    if any(k in text for k in ("not allowed", "codepoint", "invalid character", "disallowed")):
        return msg("domain_invalid_chars", lang)
    if "empty domain" in text:
        return msg("empty_domain", lang)
    return msg("domain_invalid_format", lang)


def _map_ev_error(exc: EmailNotValidError, lang: str) -> str:
    """Map an `email-validator` exception to a localised UAReady message.

    email-validator raises a single exception family with descriptive but
    English-only text. We pattern-match on the message to pick the closest
    localised key; if nothing matches we fall back to `invalid_format`
    which embeds the engine's technical detail verbatim.
    """
    text = str(exc).lower()
    # Local-part diagnostics first: dot/period errors mention "period" but
    # are about the local part, not the domain. Keep ahead of the domain
    # branch so the routing is unambiguous.
    if any(k in text for k in ("before the @-sign", "local part", "local-part")):
        if any(k in text for k in ("too long", "length")):
            return msg("local_too_long", lang)
        if "period" in text or "dot" in text:
            return msg("local_dot_position", lang)
        return msg("local_invalid_chars", lang)
    if "period" in text or "two periods" in text or " dot " in text:
        return msg("local_dot_position", lang)
    if any(k in text for k in ("idna", "punycode", "tld",
                               "after the @-sign", "domain")):
        return _map_domain_error(str(exc), lang)
    if any(k in text for k in ("too long", "length")):
        return msg("email_too_long", lang)
    return msg("invalid_format", lang, detail=str(exc))


def _pyisemail_diagnose(addr: str) -> dict:
    """Return a pyIsEmail per-RFC diagnosis dict, or an error stub.

    NOTE: pyIsEmail diagnoses against RFC 5322 only — it pre-dates EAI and
    will flag any non-ASCII local part as invalid. We surface its verdict
    verbatim and include `engine_note` so callers can show users why a
    UAReady-valid (RFC 6531) address may show as RFC 5322-invalid.
    """
    try:
        diag = _pyis_is_email(addr, check_dns=False, diagnose=True)
    except Exception as e:                          # pragma: no cover
        return {"error": f"pyIsEmail failed: {e}"}
    out = {
        "code": int(getattr(diag, "code", -1)),
        "type": getattr(diag, "diagnosis_type", None),
        "message": getattr(diag, "message", None),
        "description": getattr(diag, "description", None) or str(diag),
        "references": None,
        "engine_note": "pyIsEmail diagnoses RFC 5322 — does not implement "
                       "RFC 6531/6532 EAI; non-ASCII addresses are flagged "
                       "as invalid by this engine even when UAReady accepts them.",
    }
    try:
        refs = diag.get_references()
        out["references"] = [
            {
                "citation": getattr(r, "citation", None) or str(r),
                "url": getattr(r, "url", None),
            }
            for r in (refs or [])
        ]
    except Exception:
        pass
    return out


# ---- domain ----------------------------------------------------------------

def validate_domain(domain: str, lang: str = DEFAULT_LANG) -> dict:
    """Validate a domain per IDNA2008 + UTS#46 (non-transitional).

    Returns a dict with keys: ok, unicode, ascii, errors, warnings.
    The U-label → A-label conversion is the IDNA2008 conformance test;
    if it succeeds the domain is structurally valid.
    """
    out = {"ok": False, "unicode": None, "ascii": None,
           "errors": [], "warnings": []}
    if not isinstance(domain, str):
        out["errors"].append(msg("not_a_string", lang))
        return out
    if not domain:
        out["errors"].append(msg("empty_domain", lang))
        return out
    if _has_control(domain):
        out["errors"].append(msg("control_char", lang))
        return out

    nfc = _nfc(domain.strip())

    try:
        # uts46=True applies the IDNA compatibility mapping; transitional
        # =False follows IDNA2008 strictly (the modern, recommended path).
        ascii_form = idna.encode(nfc, uts46=True,
                                 transitional=False).decode("ascii")
    except idna.IDNAError as e:
        out["errors"].append(_map_domain_error(str(e), lang))
        return out

    if len(ascii_form) > MAX_DOMAIN_OCTETS:
        out["errors"].append(msg("domain_too_long", lang))
    for label in ascii_form.split("."):
        if len(label) > MAX_LABEL_OCTETS:
            out["errors"].append(msg("label_too_long", lang))
            break

    if "." not in ascii_form:
        out["warnings"].append(msg("domain_no_tld", lang))

    try:
        unicode_form = idna.decode(ascii_form)
    except idna.IDNAError:
        unicode_form = nfc

    out["unicode"] = unicode_form
    out["ascii"] = ascii_form
    out["ok"] = not out["errors"]
    return out


# ---- email -----------------------------------------------------------------

def validate_email(email: str, lang: str = DEFAULT_LANG,
                   diagnostics: bool = False) -> ValidationResult:
    """Validate an internationalised email address per RFC 6531 / 6532.

    Pipeline:
      1.  Type / empty pre-checks   (localised messages)
      2.  NFC normalisation         (UAX #15)
      3.  Structural split on '@'   (localised messages)
      4.  `email-validator` engine  (RFC 6531/6532, IDNA2008, UTS#46,
                                     length limits, dot rules, quoted-local)
      5.  Multi-script analysis      (informational + UTS #39 warning)
      6.  Optional pyIsEmail        (per-RFC diagnosis codes)
    """
    result = ValidationResult(
        ok=False,
        input=email if isinstance(email, str) else str(email),
    )
    if not isinstance(email, str):
        result.errors.append(msg("not_a_string", lang))
        return result

    stripped = email.strip()
    if not stripped:
        result.errors.append(msg("empty_input", lang))
        return result

    nfc = _nfc(stripped)
    result.normalized = nfc
    result.scripts = _detect_scripts(nfc)

    # --- Localised structural pre-checks ------------------------------------
    # These produce cleaner localised messages than the engine's generic
    # English text for the most common user mistakes.
    if "@" not in nfc:
        result.errors.append(msg("no_at_sign", lang))
        return result

    local, _, domain = nfc.rpartition("@")
    if not local:
        result.errors.append(msg("empty_local", lang))
    if not domain:
        result.errors.append(msg("empty_domain", lang))
    if not local or not domain:
        return result

    result.local = local

    # Stray '@' in an unquoted local part = multiple-@ error.
    if not (local.startswith('"') and local.endswith('"')) and "@" in local:
        result.errors.append(msg("multiple_at", lang))
        return result

    # RFC 5321 §4.5.3.1.1 caps the local part at 64 *octets* — email-validator
    # measures in characters, so multi-byte scripts (e.g. Devanagari at 3 B/ch)
    # can slip past its check. Enforce the octet limit ourselves first.
    if len(local.encode("utf-8")) > MAX_LOCAL_OCTETS:
        result.errors.append(msg("local_too_long", lang))
        return result

    # --- Engine: email-validator (RFC heavy lifting) ------------------------
    try:
        info = _ev_validate(
            nfc,
            check_deliverability=False,     # no DNS — that's the MX stretch
            allow_smtputf8=True,            # RFC 6531
            allow_quoted_local=True,        # RFC 5321 quoted local
            globally_deliverable=False,     # don't require IANA TLD list
        )
    except EmailNotValidError as e:
        result.errors.append(_map_ev_error(e, lang))
        return result

    # email-validator gives us normalised forms — prefer them.
    result.local = info.local_part
    result.normalized = info.normalized
    result.domain_unicode = info.domain
    result.domain_ascii = info.ascii_domain
    result.smtputf8_required = bool(info.smtputf8)
    result.idn_required = bool(
        info.ascii_domain and info.ascii_domain != info.domain
    )

    # --- UTS #39 inspired mixed-script warning -----------------------------
    # 2+ scripts in the local part is a potential homograph signal.
    # Surface as a warning (not an error) so genuine multi-script names
    # (e.g. "john.राम@…") still validate.
    local_scripts = _detect_scripts(local)
    if len(local_scripts) >= 2:
        result.warnings.append(
            msg("mixed_scripts_local", lang,
                scripts=", ".join(local_scripts))
        )

    # Mirror domain-side warnings for output parity with validate_domain.
    if info.ascii_domain and "." not in info.ascii_domain:
        result.warnings.append(msg("domain_no_tld", lang))

    # --- Optional per-RFC diagnosis (pyIsEmail) -----------------------------
    if diagnostics and _PYIS_AVAILABLE:
        result.diagnosis = _pyisemail_diagnose(nfc)

    result.ok = not result.errors
    return result


# ---- stretch goal: DNS / MX lookup -----------------------------------------

def lookup_mx(domain_ascii: str, timeout: float = 3.0):
    """Resolve MX records for an A-label (punycode) domain.

    Stretch goal: confirms an IDN domain actually resolves and accepts mail.
    Raises if DNS fails; caller decides how to surface the error.
    """
    import dns.resolver
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    answers = resolver.resolve(domain_ascii, "MX")
    return sorted([(int(r.preference),
                    r.exchange.to_text(omit_final_dot=True))
                   for r in answers])


def resolve_a(domain_ascii: str, timeout: float = 3.0):
    """Resolve A/AAAA records for an A-label domain."""
    import dns.resolver
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    addrs = []
    for rtype in ("A", "AAAA"):
        try:
            addrs.extend([(rtype, r.to_text())
                          for r in resolver.resolve(domain_ascii, rtype)])
        except Exception:
            pass
    return addrs
