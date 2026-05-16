# UAReady

**Internationalised email & domain validator** built for the
*UA Adaptation and Hackathon Nepal 2026 — Technical Track*.

> "The same email address. The same domain. Working everywhere —
> in every language, every script."

UAReady accepts addresses such as `राम@नेपाल.नेपाल`, normalises and
encodes them per the relevant RFCs, and returns a single answer
together with a structured breakdown that downstream code can act on.
It ships as a Python library, a CLI, and a small HTTP API with a
browser demo.

---

## Standards implemented

| Standard | What UAReady does |
|---|---|
| **RFC 6531 — SMTPUTF8** | flags mailboxes that require an SMTPUTF8-capable server (non-ASCII local part) |
| **RFC 6532 — EAI**     | accepts any non-ASCII Unicode in the local part except control / separator categories |
| **RFC 5321 — SMTP**    | enforces 64-octet local, 253-octet domain, 254-octet total, 63-octet label limits |
| **RFC 5891 / IDNA2008** | encodes domains via `idna` reference library (non-transitional) |
| **UTS #46**            | compatibility mapping applied before IDNA encoding |
| **Unicode NFC**        | input normalised before comparison or encoding |

---

## Repository layout

```
uaready/
  __init__.py          public API (validate_email, validate_domain, ...)
  validator.py         core validation logic
  errors.py            localised error messages (en, ne, hi, ar)
  cli.py               command-line interface
  server.py            Flask API + browser demo
  static/index.html    browser demo
  requirements.txt     uaready dependencies
tests/
  test_uaready.py      valid + invalid + standards-compliance cases
UAREADY.md             this file
```

---

## Setup

Requires Python 3.9+.

```bash
pip install -r uaready/requirements.txt
```

That installs:

- [`idna`](https://pypi.org/project/idna/) — IDNA2008 reference implementation
- `flask` — for the HTTP API / browser demo
- `dnspython` — for the MX-lookup stretch goal

---

## Usage

### 1. Python library

```python
from uaready import validate_email, validate_domain

r = validate_email("राम@नेपाल.नेपाल")
print(r.ok)                  # True
print(r.domain_ascii)        # xn--11b7c.xn--11b7c
print(r.scripts)             # ['Devanagari']
print(r.smtputf8_required)   # True   (mailbox is non-ASCII)
print(r.idn_required)        # True   (domain is non-ASCII)

bad = validate_email("user@@example.com", lang="ne")
print(bad.errors)            # ['इमेलमा एक भन्दा बढी \'@\' छन्।']

d = validate_domain("नेपाल.नेपाल")
print(d["ascii"])            # xn--11b7c.xn--11b7c
print(d["unicode"])          # नेपाल.नेपाल
```

The `ValidationResult` dataclass exposes:

| field | meaning |
|---|---|
| `ok` | overall verdict |
| `input` | original input |
| `normalized` | NFC-normalised form |
| `local`, `domain_unicode`, `domain_ascii` | split parts |
| `smtputf8_required` | mailbox needs RFC 6531 transport |
| `idn_required` | domain was punycoded |
| `errors`, `warnings` | localised strings |
| `scripts` | detected scripts (Devanagari, Arabic, Cyrillic, ...) |

### 2. CLI

```bash
python -m uaready ram@example.np
python -m uaready राम@नेपाल.नेपाल --lang ne
python -m uaready नेपाल.नेपाल --domain
python -m uaready ram@gmail.com --mx --json
echo "user@example.np" | python -m uaready
```

Exit code is `0` for valid input, `1` otherwise — friendly to shell
pipelines and CI checks.

### 3. HTTP API + browser demo

```bash
python -m uaready.server
# → http://127.0.0.1:8080
```

Endpoints:

| Method | Path | Body | Purpose |
|---|---|---|---|
| `GET`  | `/` | — | Browser demo |
| `POST` | `/api/validate` | `{"value": "...", "kind": "email"\|"domain", "lang": "en", "mx": false}` | Validate input |
| `POST` | `/api/mx` | `{"domain": "..."}` | DNS MX lookup |
| `GET`  | `/api/health` | — | liveness probe |

Example:

```bash
curl -s -X POST http://127.0.0.1:8080/api/validate \
     -H 'Content-Type: application/json' \
     -d '{"value": "राम@नेपाल.नेपाल"}' | jq
```

---

## Scripts supported

Tested explicitly: **Latin**, **Devanagari** (priority — Nepal relevance),
**Arabic**, **Cyrillic**, **CJK**.

Anything supported by IDNA2008 and `unicodedata` is accepted in
principle; the explicit list above is what the test suite exercises.

---

## Nepal relevance

- `.नेपाल` (the Devanagari Nepali ccTLD) round-trips cleanly to its
  A-label form and back, with NFC normalisation applied at the
  boundary.
- Devanagari mailbox names (e.g. `राम@`) are accepted per RFC 6532
  and flagged as requiring an SMTPUTF8-capable mail server, which is
  exactly the signal a sending application needs to decide whether
  to negotiate the `SMTPUTF8` extension at `EHLO` time.
- Error messages are localised to Nepali, Hindi, Arabic, and English.

---

## Test suite

```bash
python -m unittest tests.test_uaready -v
```

`tests/test_uaready.py` covers:

- **6 valid emails** spanning Latin, Devanagari, Arabic, Cyrillic, CJK
- **6 valid domains** including `.नेपाल` and already-punycoded input
- **9 invalid emails** (empty, missing `@`, multiple `@`, empty parts,
  bad dot positions, IDNA failures, spaces)
- **5 invalid domains** (empty, leading/trailing hyphens, spaces,
  over-long labels)
- **Standards-compliance** assertions: NFC, IDNA punycode round-trip,
  SMTPUTF8 flag, IDN flag, localisation, length limits, script
  detection.

---

## Known limits

- **Quoted local parts** (RFC 5321 §4.1.2 quoted-string form) are
  accepted verbatim; the inner character set is not strictly checked.
  Quoted forms are very rare in practice and almost never appear in
  EAI deployments.
- **DNSSEC / MTA-STS** validation is out of scope — the MX lookup
  stretch goal only confirms records exist.
- **Display-name** parsing (e.g. `"राम" <ram@...>`) is not handled;
  callers should strip the display name first.
- **Confusable / homograph detection** is not part of this tool —
  for that, see the sibling [`sushasan`](./sushasan.py) project in this
  repository.

---

## License

Apache 2.0 — same as the surrounding repository.
