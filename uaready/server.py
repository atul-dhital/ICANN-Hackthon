"""Flask API + browser demo for UAReady.

Run:
    python -m uaready.server
    PORT=8080 HOST=0.0.0.0 python -m uaready.server
"""

import os
from flask import Flask, request, jsonify, send_from_directory

from .validator import validate_email, validate_domain, lookup_mx

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


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


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "uaready"})


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8080))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
