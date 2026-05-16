"""UAReady — internationalised email & domain validation.

Standards implemented:
  - RFC 6531  (SMTPUTF8)             internationalised SMTP extension
  - RFC 6532  (EAI)                  Internationalised Email Headers
  - RFC 5321  (SMTP)                 length & syntax limits
  - RFC 5891 / IDNA2008              international domain names
  - UTS #46                          unicode IDNA compatibility mapping
  - Unicode NFC                      normalisation for stable comparison
"""

import unicodedata
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import idna  # IDNA2008 reference implementation

from .errors import msg, DEFAULT_LANG


# RFC 5322 atext (extended by RFC 6532 to allow any non-ASCII Unicode)
ATEXT_ASCII = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "!#$%&'*+-/=?^_`{|}~"
)

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

    def to_dict(self):
        return asdict(self)


# ---- helpers ---------------------------------------------------------------

def _detect_scripts(s: str) -> List[str]:
    """Best-effort script identification by Unicode name prefix."""
    seen = set()
    for ch in s:
        if ch == "@" or ch == ".":
            continue
        if ch.isascii():
            if ch.isalpha():
                seen.add("Latin")
            continue
        try:
            name = unicodedata.name(ch, "")
        except ValueError:
            continue
        if "DEVANAGARI" in name:
            seen.add("Devanagari")
        elif "ARABIC" in name:
            seen.add("Arabic")
        elif "CYRILLIC" in name:
            seen.add("Cyrillic")
        elif "TAMIL" in name:
            seen.add("Tamil")
        elif "BENGALI" in name:
            seen.add("Bengali")
        elif "GREEK" in name:
            seen.add("Greek")
        elif "HEBREW" in name:
            seen.add("Hebrew")
        elif "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name or "HANGUL" in name:
            seen.add("CJK")
        else:
            seen.add("Other")
    return sorted(seen)


def _has_control(s: str) -> bool:
    return any(unicodedata.category(c).startswith("C") for c in s)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ---- domain ----------------------------------------------------------------

def validate_domain(domain: str, lang: str = DEFAULT_LANG) -> dict:
    """Validate a domain per IDNA2008 + UTS#46 (non-transitional).

    Returns a dict with keys: ok, unicode, ascii, errors, warnings.
    """
    out = {"ok": False, "unicode": None, "ascii": None, "errors": [], "warnings": []}
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
        # uts46=True applies the IDNA compatibility mapping; transitional=False
        # follows IDNA2008 strictly (the modern, recommended behaviour).
        ascii_form = idna.encode(nfc, uts46=True, transitional=False).decode("ascii")
    except idna.IDNAError as e:
        out["errors"].append(msg("idna_failed", lang, detail=str(e)))
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


# ---- local part ------------------------------------------------------------

def _validate_local(local: str, lang: str) -> List[str]:
    errors: List[str] = []
    if not local:
        errors.append(msg("empty_local", lang))
        return errors
    if _has_control(local):
        errors.append(msg("control_char", lang))
        return errors
    if len(local.encode("utf-8")) > MAX_LOCAL_OCTETS:
        errors.append(msg("local_too_long", lang))

    # Quoted local part (RFC 5321) — accept verbatim; rare in EAI.
    if local.startswith('"') and local.endswith('"') and len(local) >= 2:
        return errors

    if local.startswith(".") or local.endswith(".") or ".." in local:
        errors.append(msg("local_dot_position", lang))

    for ch in local:
        if ch == ".":
            continue
        if ch.isascii():
            if ch not in ATEXT_ASCII:
                errors.append(msg("local_invalid_chars", lang))
                break
        else:
            # RFC 6532 §3.1: any non-ASCII Unicode is allowed in mailbox local
            # part — except control / format / separator characters.
            cat = unicodedata.category(ch)
            if cat[0] in ("C", "Z"):
                errors.append(msg("local_invalid_chars", lang))
                break
    return errors


# ---- email -----------------------------------------------------------------

def validate_email(email: str, lang: str = DEFAULT_LANG) -> ValidationResult:
    """Validate an internationalised email address per RFC 6531 / 6532."""
    result = ValidationResult(ok=False, input=email if isinstance(email, str) else str(email))
    if not isinstance(email, str):
        result.errors.append(msg("not_a_string", lang))
        return result
    stripped = email.strip()
    if not stripped:
        result.errors.append(msg("empty_input", lang))
        return result

    nfc = _nfc(stripped)
    result.normalized = nfc

    if "@" not in nfc:
        result.errors.append(msg("no_at_sign", lang))
        return result

    # split at the rightmost @ so quoted local parts may contain literal @
    local, _, domain = nfc.rpartition("@")
    if not local:
        result.errors.append(msg("empty_local", lang))
    if not domain:
        result.errors.append(msg("empty_domain", lang))
    if not local or not domain:
        return result

    result.local = local

    # detect stray @ in unquoted local
    if not (local.startswith('"') and local.endswith('"')) and "@" in local:
        result.errors.append(msg("multiple_at", lang))

    result.errors.extend(_validate_local(local, lang))

    domain_check = validate_domain(domain, lang=lang)
    result.errors.extend(domain_check["errors"])
    result.warnings.extend(domain_check["warnings"])
    result.domain_unicode = domain_check["unicode"]
    result.domain_ascii = domain_check["ascii"]

    if len(nfc.encode("utf-8")) > MAX_EMAIL_OCTETS:
        result.errors.append(msg("email_too_long", lang))

    # SMTPUTF8 (RFC 6531) is required when the *mailbox* local-part contains
    # any non-ASCII characters; the domain side is handled by IDN punycode
    # so it does not itself trigger SMTPUTF8.
    result.smtputf8_required = any(ord(c) > 127 for c in local)
    result.idn_required = bool(
        domain_check["ascii"] and domain_check["ascii"] != domain
    )

    result.scripts = _detect_scripts(nfc)
    result.ok = not result.errors
    return result


# ---- stretch goal: DNS / MX lookup -----------------------------------------

def lookup_mx(domain_ascii: str, timeout: float = 3.0):
    """Resolve MX records for an A-label (punycode) domain.

    Stretch goal: confirms an IDN domain actually resolves and accepts mail.
    Raises if DNS fails; caller decides how to surface the error.
    """
    import dns.resolver  # imported lazily so the core module has no DNS dep
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    answers = resolver.resolve(domain_ascii, "MX")
    return sorted([(int(r.preference), r.exchange.to_text(omit_final_dot=True))
                   for r in answers])


def resolve_a(domain_ascii: str, timeout: float = 3.0):
    """Resolve A/AAAA records for an A-label domain."""
    import dns.resolver
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    addrs = []
    for rtype in ("A", "AAAA"):
        try:
            addrs.extend([(rtype, r.to_text()) for r in resolver.resolve(domain_ascii, rtype)])
        except Exception:
            pass
    return addrs
