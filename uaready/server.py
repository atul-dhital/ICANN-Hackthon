"""Flask API + browser demo for UAReady.

Run:
    python -m uaready.server
    PORT=8080 HOST=0.0.0.0 python -m uaready.server
"""

import ipaddress
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTPUTF8
from email.utils import formataddr
from urllib.parse import urlsplit

from flask import Flask, request, jsonify, send_from_directory

from .sendmail import SmtpConfig
from .validator import validate_email, validate_domain, lookup_mx, resolve_a

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
ROOT_DIR = os.path.dirname(HERE)
MAIL_UI_DIR = os.path.join(ROOT_DIR, "frontend")
LINK_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>'\"]+", re.IGNORECASE)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


# ---- link extraction & domain check ----------------------------------------

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
        recipient_result = validate_email(to, lang=lang)
        recipient = recipient_result.to_dict()
        if recipient.get("ok"):
            warnings.extend(recipient.get("warnings") or [])
            errors.extend(_recipient_delivery_issues(recipient_result))
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


# ---- SMTP helpers ----------------------------------------------------------

SMTP_TRANSPORT_ENV_KEYS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
    "SMTP_FROM_EMAIL",
)


def _smtp_settings():
    timeout = float(os.environ.get("SMTP_TIMEOUT", 15))
    from_name = os.environ.get("SMTP_FROM_NAME", "UAReady Mailer").strip()

    if any(os.environ.get(key) for key in SMTP_TRANSPORT_ENV_KEYS):
        username = os.environ.get("SMTP_USERNAME", "").strip()
        from_email = os.environ.get("SMTP_FROM_EMAIL", "").strip() or username or "no-reply@example.com"
        return {
            "host": os.environ.get("SMTP_HOST", "").strip(),
            "port": int(os.environ.get("SMTP_PORT", 587)),
            "username": username,
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "use_tls": os.environ.get("SMTP_USE_TLS", "1").lower() not in {"0", "false", "no"},
            "use_ssl": os.environ.get("SMTP_USE_SSL", "0").lower() in {"1", "true", "yes"},
            "from_email": from_email,
            "from_name": from_name,
            "timeout": timeout,
        }

    try:
        cfg = SmtpConfig.load()
    except RuntimeError as exc:
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_* env vars or configure "
            "uaready/sendmail.ini / UAREADY_* env vars."
        ) from exc

    return {
        "host": cfg.server,
        "port": cfg.port,
        "username": cfg.username,
        "password": cfg.password,
        "use_tls": cfg.ssl_mode == "starttls",
        "use_ssl": cfg.ssl_mode == "ssl",
        "from_email": (cfg.default_from or cfg.username).strip(),
        "from_name": from_name,
        "timeout": timeout,
    }


def _recipient_delivery_issues(recipient_result) -> list[str]:
    domain_ascii = (recipient_result.domain_ascii or "").strip()
    if not domain_ascii:
        return ["Recipient email is missing a usable mail domain."]
    if "." not in domain_ascii:
        return ["Recipient email must use a fully qualified mail domain."]

    try:
        mx_records = lookup_mx(domain_ascii)
    except Exception:
        mx_records = []

    if mx_records:
        return []

    try:
        fallback_hosts = resolve_a(domain_ascii)
    except Exception:
        fallback_hosts = []

    if fallback_hosts:
        return []

    return [f"Recipient domain does not resolve to a reachable mail host: {domain_ascii}"]


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
        client = smtplib.SMTP_SSL(
            settings["host"], settings["port"],
            timeout=settings["timeout"],
            context=ssl.create_default_context(),
        )
        client.ehlo()
    else:
        client = smtplib.SMTP(settings["host"], settings["port"], timeout=settings["timeout"])
        client.ehlo()
        if settings["use_tls"]:
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
    if settings["username"]:
        client.login(settings["username"], settings["password"])
    return client


# ---- routes ----------------------------------------------------------------

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
    """Validate the whole composition (recipient + links + required fields)
    then send via SMTPUTF8 using environment-configured SMTP credentials.

    Honours both `recipient` (test/frontend) and `to` (CLI) payload keys.
    """
    payload = request.get_json(force=True, silent=True) or {}

    # Step 1: localised, full-composition pre-flight check.
    compose = _validate_compose_payload(payload)
    if not compose["ok"]:
        return jsonify({
            "ok": False,
            "error": compose["errors"][0] if compose["errors"] else "invalid composition",
            "errors": compose["errors"],
            "warnings": compose["warnings"],
            "links": compose["links"],
            "recipient": compose["recipient"],
        }), 400

    clean = compose["payload"]
    recipient = clean["to"]
    subject = clean["subject"]
    body = clean["body"]
    sender_name = clean["sender_name"]

    # Step 2: SMTP envelope prep.
    recipient_validation = validate_email(recipient)
    settings = _smtp_settings()
    sender_validation = validate_email(settings["from_email"])
    if not sender_validation.ok:
        return jsonify({
            "ok": False,
            "error": "invalid sender configuration",
            "details": sender_validation.errors,
        }), 500

    recipient_address = _message_address(recipient_validation, recipient)
    sender_address = _message_address(sender_validation, settings["from_email"])
    needs_utf8 = _needs_smtputf8(recipient_address, sender_address)

    message = EmailMessage(policy=SMTPUTF8) if needs_utf8 else EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((sender_name or settings["from_name"], sender_address))
    message["To"] = recipient_address
    message.set_content(body)

    mail_options = ["SMTPUTF8"] if needs_utf8 else []

    # Step 3: deliver.
    advertised = False
    try:
        with _open_smtp(settings) as client:
            advertised = bool(client.has_extn("smtputf8"))
            if needs_utf8 and not advertised:
                raise smtplib.SMTPNotSupportedError(
                    "SMTPUTF8 is required but the server does not advertise it"
                )
            client.send_message(
                message,
                from_addr=sender_address,
                to_addrs=[recipient_address],
                mail_options=mail_options,
            )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify({
        "ok": True,
        "recipient": recipient_address,
        "sender": sender_address,
        "smtp_utf8_required": needs_utf8,
        # Aliases for the /mail/ frontend, which keys off these names.
        "smtputf8_used": needs_utf8,
        "smtputf8_advertised": advertised,
        "message_id": message.get("Message-ID"),
        "links": compose["links"],
        "links_checked": len(compose["links"]),
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
