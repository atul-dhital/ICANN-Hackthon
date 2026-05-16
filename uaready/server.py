"""Flask API + browser demo for UAReady.

Run:
    python -m uaready.server
    PORT=8080 HOST=0.0.0.0 python -m uaready.server
"""

import os
import ssl
import smtplib
from email.message import EmailMessage
from email.policy import SMTPUTF8
from email.utils import formataddr

from flask import Flask, request, jsonify, send_from_directory

from .validator import validate_email, validate_domain, lookup_mx

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATIC_DIR = os.path.join(ROOT, "frontend")
if not os.path.isdir(STATIC_DIR):
    STATIC_DIR = os.path.join(HERE, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


def _smtp_settings():
    return {
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "username": os.environ.get("SMTP_USERNAME", "").strip(),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "use_tls": os.environ.get("SMTP_USE_TLS", "1").lower() not in {"0", "false", "no"},
        "use_ssl": os.environ.get("SMTP_USE_SSL", "0").lower() in {"1", "true", "yes"},
        "from_email": os.environ.get("SMTP_FROM_EMAIL", "no-reply@example.com").strip(),
        "from_name": os.environ.get("SMTP_FROM_NAME", "UAReady Mailer").strip(),
        "timeout": float(os.environ.get("SMTP_TIMEOUT", 15)),
    }


def _message_address(validation, original):
    if validation.smtputf8_required:
        return validation.normalized or original
    if validation.domain_ascii and validation.local and "@" in original:
        return f"{validation.local}@{validation.domain_ascii}"
    return validation.normalized or original


def _needs_smtputf8(*values):
    return any(any(ord(ch) > 127 for ch in value) for value in values if isinstance(value, str))


def _open_smtp(settings):
    if not settings["host"]:
        raise RuntimeError("SMTP_HOST is not configured")

    if settings["use_ssl"]:
        client = smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=settings["timeout"], context=ssl.create_default_context())
    else:
        client = smtplib.SMTP(settings["host"], settings["port"], timeout=settings["timeout"])
        if settings["use_tls"]:
            client.starttls(context=ssl.create_default_context())

    client.ehlo()
    if settings["username"]:
        client.login(settings["username"], settings["password"])
    return client


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


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


@app.route("/api/send", methods=["POST"])
def api_send():
    payload = request.get_json(force=True, silent=True) or {}
    recipient = (payload.get("recipient") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = payload.get("body") or ""
    sender_name = (payload.get("sender_name") or "").strip()

    if not recipient:
        return jsonify({"ok": False, "error": "recipient required"}), 400
    if not subject:
        return jsonify({"ok": False, "error": "subject required"}), 400
    if not body.strip():
        return jsonify({"ok": False, "error": "body required"}), 400

    recipient_validation = validate_email(recipient)
    if not recipient_validation.ok:
        return jsonify({"ok": False, "error": "invalid recipient", "details": recipient_validation.errors}), 400

    settings = _smtp_settings()
    sender_validation = validate_email(settings["from_email"])
    if not sender_validation.ok:
        return jsonify({"ok": False, "error": "invalid sender configuration", "details": sender_validation.errors}), 500

    recipient_address = _message_address(recipient_validation, recipient)
    sender_address = _message_address(sender_validation, settings["from_email"])
    needs_utf8 = _needs_smtputf8(recipient_address, sender_address)

    message = EmailMessage(policy=SMTPUTF8) if needs_utf8 else EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((sender_name or settings["from_name"], sender_address))
    message["To"] = recipient_address
    message.set_content(body)

    mail_options = []
    if needs_utf8:
        mail_options.append("SMTPUTF8")

    try:
        with _open_smtp(settings) as client:
            if needs_utf8 and not client.has_extn("smtputf8"):
                raise smtplib.SMTPNotSupportedError("SMTPUTF8 is required but the server does not advertise it")
            client.send_message(message, from_addr=sender_address, to_addrs=[recipient_address], mail_options=mail_options)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify({
        "ok": True,
        "recipient": recipient_address,
        "sender": sender_address,
        "smtp_utf8_required": needs_utf8,
    })


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


@app.route("/api/send", methods=["POST"])
def api_send():
    """Stretch goal: live SMTPUTF8 send. Requires uaready/sendmail.ini."""
    from .sendmail import send
    payload = request.get_json(force=True, silent=True) or {}
    to = (payload.get("to") or "").strip()
    subject = payload.get("subject") or "UAReady test — SMTPUTF8"
    body = payload.get("body") or "UAReady SMTPUTF8 live-send test."
    sender = (payload.get("from") or "").strip() or None
    if not to:
        return jsonify({"ok": False, "error": "'to' is required"}), 400
    try:
        res = send(to, subject, body, sender=sender)
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({
        "ok": res.ok,
        "to": to,
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
