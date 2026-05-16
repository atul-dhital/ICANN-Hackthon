"""Command-line interface for UAReady.

Usage:
    python -m uaready.cli ram@example.np
    python -m uaready.cli राम@नेपाल.नेपाल --lang ne
    python -m uaready.cli नेपाल.नेपाल --domain
    python -m uaready.cli ram@gmail.com --mx --json
    echo "user@example.np" | python -m uaready.cli
"""

import argparse
import json
import sys

from .validator import validate_email, validate_domain, lookup_mx


def _emit_human(r: dict) -> None:
    pad = "  "
    print(f"Input: {r.get('input')}")
    print(f"{pad}Valid: {r.get('ok')}")
    if r.get("local"):
        print(f"{pad}Local: {r['local']}")
    udom = r.get("domain_unicode") or r.get("unicode")
    adom = r.get("domain_ascii") or r.get("ascii")
    if udom:
        print(f"{pad}Domain (Unicode): {udom}")
    if adom:
        print(f"{pad}Domain (ASCII):   {adom}")
    if r.get("scripts"):
        print(f"{pad}Scripts: {', '.join(r['scripts'])}")
    if "smtputf8_required" in r:
        print(f"{pad}SMTPUTF8 required: {r['smtputf8_required']}")
    if "idn_required" in r:
        print(f"{pad}IDN encoding used: {r['idn_required']}")
    for w in r.get("warnings") or []:
        print(f"{pad}! {w}")
    for e in r.get("errors") or []:
        print(f"{pad}x {e}")
    if r.get("mx"):
        print(f"{pad}MX:")
        for pref, host in r["mx"]:
            print(f"{pad}  {pref:>4}  {host}")
    if r.get("mx_error"):
        print(f"{pad}MX lookup error: {r['mx_error']}")
    print()


def _force_utf8_stdout():
    """Windows consoles default to cp1252, which mangles non-Latin scripts.
    Re-encode stdout/stderr as UTF-8 so Devanagari, Arabic etc. print cleanly."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _force_utf8_stdout()
    p = argparse.ArgumentParser(
        prog="uaready",
        description="Validate internationalised email addresses and domain names "
                    "(SMTPUTF8 / EAI / IDNA2008 / UTS#46 / NFC).",
    )
    p.add_argument("input", nargs="?", help="Email or domain to validate "
                   "(reads stdin lines if omitted)")
    p.add_argument("--domain", action="store_true", help="Treat input as domain only")
    p.add_argument("--lang", default="en", help="Error language (en, ne, hi, ar)")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--mx", action="store_true", help="Resolve MX records (stretch goal)")
    args = p.parse_args(argv)

    targets = [args.input] if args.input else [
        line.strip() for line in sys.stdin if line.strip()
    ]

    rc = 0
    results = []
    for t in targets:
        if args.domain:
            d = validate_domain(t, lang=args.lang)
            r = {"input": t, **d}
        else:
            r = validate_email(t, lang=args.lang).to_dict()

        adom = r.get("domain_ascii") or r.get("ascii")
        if args.mx and r.get("ok") and adom:
            try:
                r["mx"] = lookup_mx(adom)
            except Exception as e:
                r["mx_error"] = str(e)

        if not r.get("ok"):
            rc = 1
        results.append(r)

    if args.json:
        out = results if len(results) > 1 else (results[0] if results else {})
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for r in results:
            _emit_human(r)

    sys.exit(rc)


if __name__ == "__main__":
    main()
