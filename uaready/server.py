"""Flask API + browser demo for UAReady.

Run:
    python -m uaready.server
    PORT=8080 HOST=0.0.0.0 python -m uaready.server
"""

import ipaddress
import os
import re
from urllib.parse import urlsplit

from flask import Flask, request, jsonify, send_from_directory

from .validator import validate_email, validate_domain, lookup_mx

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
ROOT_DIR = os.path.dirname(HERE)
MAIL_UI_DIR = os.path.join(ROOT_DIR, "frontend")
LINK_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>'\"]+", re.IGNORECASE)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


def _extract_links(*texts):
    links = []
    seen = set()
    for text in texts:
        for match in LINK_RE.finditer(text or ""):
            url = match.group(0).rstrip(".,;:!?)]}")
            if url and url not in seen:
                seen.add(url)
                links.append(url)
    return links


def _validate_link(url: str, lang: str = "en"):
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError:
        return f"Link has an invalid port: {url}"

    scheme = (parts.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return f"Link must use http:// or https://: {url}"

    hostname = parts.hostname
    if not hostname:
        return f"Link is missing a host name: {url}"

    if hostname != "localhost":
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            domain_check = validate_domain(hostname, lang=lang)
            if not domain_check["ok"]:
                detail = "; ".join(domain_check["errors"])
                return f"Link domain is invalid: {url} ({detail})"

    return None


def _validate_compose_payload(payload: dict) -> dict:
    lang = (payload.get("lang") or "en").strip() or "en"
    to = (payload.get("to") or payload.get("recipient") or "").strip()
    sender = (payload.get("from") or "").strip() or None
    sender_name = (payload.get("sender_name") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = payload.get("body") or ""

    errors = []
    warnings = []
    recipient = None

    if not to:
        errors.append("Recipient email is required.")
    else:
        recipient = validate_email(to, lang=lang).to_dict()
        if recipient.get("ok"):
            warnings.extend(recipient.get("warnings") or [])
        else:
            errors.extend(recipient.get("errors") or ["Recipient email is invalid."])

    if sender:
        sender_result = validate_email(sender, lang=lang)
        if not sender_result.ok:
            errors.extend([f"Sender address is invalid: {detail}" for detail in sender_result.errors])

    if not subject:
        errors.append("Subject is required.")
    if not body.strip():
        errors.append("Message body is required.")

    links = _extract_links(subject, body)
    for url in links:
        link_error = _validate_link(url, lang=lang)
        if link_error:
            errors.append(link_error)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "links": links,
        "recipient": recipient,
        "payload": {
            "to": to,
            "from": sender,
            "sender_name": sender_name,
            "subject": subject,
            "body": body,
            "lang": lang,
        },
    }


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/mail/")
def mail_index():
    return send_from_directory(MAIL_UI_DIR, "index.html")


@app.route("/mail/<path:asset>")
def mail_asset(asset):
    return send_from_directory(MAIL_UI_DIR, asset)


@app.route("/api/validate", methods=["POST"])
def api_validate():
    payload = request.get_json(force=True, silent=True) or {}
    value = (payload.get("value") or "").strip()
    kind = payload.get("kind", "email")
    lang = payload.get("lang", "en")
    want_mx = bool(payload.get("mx"))

    if not value:
        return jsonify({"ok": False, "errors": ["empty input"]}), 400

    if kind == "domain":
        result = {"input": value, **validate_domain(value, lang=lang)}
    else:
        result = validate_email(value, lang=lang).to_dict()

    adom = result.get("domain_ascii") or result.get("ascii")
    if want_mx and result.get("ok") and adom:
        try:
            result["mx"] = lookup_mx(adom)
        except Exception as e:
            result["mx_error"] = str(e)

    return jsonify(result)


@app.route("/api/mx", methods=["POST"])
def api_mx():
    payload = request.get_json(force=True, silent=True) or {}
    domain = (payload.get("domain") or "").strip()
    if not domain:
        return jsonify({"error": "domain required"}), 400
    res = validate_domain(domain)
    if not res["ok"]:
        return jsonify({"error": "invalid domain", "details": res["errors"]}), 400
    try:
        mx = lookup_mx(res["ascii"])
    except Exception as e:
        return jsonify({"ok": False, "domain": res["ascii"], "error": str(e)}), 200
    return jsonify({"ok": True, "domain": res["ascii"], "mx": mx})


@app.route("/api/compose/validate", methods=["POST"])
def api_compose_validate():
    payload = request.get_json(force=True, silent=True) or {}
    result = _validate_compose_payload(payload)
    status = 200 if result["ok"] else 400
    return jsonify({
        "ok": result["ok"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "links": result["links"],
        "recipient": result["recipient"],
    }), status


@app.route("/api/send", methods=["POST"])
def api_send():
    """Stretch goal: live SMTPUTF8 send. Requires uaready/sendmail.ini."""
    from .sendmail import send
    payload = request.get_json(force=True, silent=True) or {}
    compose = _validate_compose_payload(payload)
    if not compose["ok"]:
        return jsonify({
            "ok": False,
            "errors": compose["errors"],
            "warnings": compose["warnings"],
            "links": compose["links"],
            "recipient": compose["recipient"],
        }), 400

    clean = compose["payload"]
    try:
        res = send(clean["to"], clean["subject"], clean["body"], sender=clean["from"])
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({
        "ok": res.ok,
        "recipient": clean["to"],
        "links": compose["links"],
        "links_checked": len(compose["links"]),
        "smtputf8_advertised": res.smtputf8_advertised,
        "smtputf8_used": res.smtputf8_used,
        "message_id": res.message_id,
        "error": res.error,
    })


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "uaready"})


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8080))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
