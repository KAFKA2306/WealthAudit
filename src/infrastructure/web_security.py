from __future__ import annotations

import hmac
import os
import secrets
from urllib.parse import urlsplit

from flask import Flask, Response, request
from plotly.offline.offline import get_plotlyjs

DEFAULT_MAX_CONTENT_LENGTH = 64 * 1024
MAX_GRAPH_MONTHS = 120
MAX_FORECAST_MONTHS = 120
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
HTMX_URL = "https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"
HTMX_INTEGRITY = "sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"
PLOTLY_CDN_TAG = '<script src="https://cdn.plot.ly/plotly-3.3.0.min.js" defer></script>'
PLOTLY_LOCAL_TAG = '<script src="/static/vendor/plotly.min.js" defer></script>'
HTMX_LEGACY_TAG = '<script src="https://unpkg.com/htmx.org@2.0.1" defer></script>'
HTMX_PINNED_TAG = (
    f'<script src="{HTMX_URL}" integrity="{HTMX_INTEGRITY}" '
    'crossorigin="anonymous" defer></script>'
)


def _same_origin() -> bool:
    origin = request.headers.get("Origin")
    if not origin:
        return True
    supplied = urlsplit(origin)
    expected = urlsplit(request.host_url)
    return (supplied.scheme, supplied.netloc) == (expected.scheme, expected.netloc)


def _basic_auth_response() -> Response:
    response = Response("Authentication required.", status=401)
    response.headers["WWW-Authenticate"] = 'Basic realm="WealthAudit", charset="UTF-8"'
    return response


def _bounded_positive_integer(name: str, maximum: int) -> Response | None:
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return Response(f"Invalid {name} parameter.", status=400)
    if value < 1 or value > maximum:
        return Response(f"Invalid {name} parameter.", status=400)
    return None


def apply_web_security(app: Flask) -> None:
    """Install the fail-closed HTTP boundary for personal financial routes."""

    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("WEALTHAUDIT_MAX_REQUEST_BYTES", DEFAULT_MAX_CONTENT_LENGTH)
    )
    access_token = os.environ.get("WEALTHAUDIT_ACCESS_TOKEN", "")
    csrf_token = os.environ.get("WEALTHAUDIT_CSRF_TOKEN") or secrets.token_urlsafe(32)
    app.jinja_env.globals["wealthaudit_csrf_token"] = lambda: csrf_token

    def serve_plotly_vendor() -> Response:
        response = Response(get_plotlyjs(), mimetype="application/javascript")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    app.add_url_rule(
        "/static/vendor/plotly.min.js",
        endpoint="wealthaudit_plotly_vendor",
        view_func=serve_plotly_vendor,
        methods=["GET"],
    )

    @app.before_request
    def enforce_web_boundary() -> Response | None:
        if request.endpoint in {"static", "wealthaudit_plotly_vendor"}:
            return None

        if not access_token:
            return Response(
                "WealthAudit access token is not configured.",
                status=503,
            )

        auth = request.authorization
        supplied_token = auth.password if auth is not None else ""
        if not supplied_token or not hmac.compare_digest(supplied_token, access_token):
            return _basic_auth_response()

        if request.method not in SAFE_METHODS:
            if not _same_origin():
                return Response("Cross-origin request rejected.", status=403)
            supplied_csrf = request.form.get("csrf_token") or request.headers.get(
                "X-CSRF-Token", ""
            )
            if not supplied_csrf or not hmac.compare_digest(supplied_csrf, csrf_token):
                return Response("CSRF validation failed.", status=403)

        if request.path.startswith("/graphs/"):
            invalid = _bounded_positive_integer("months", MAX_GRAPH_MONTHS)
            if invalid is not None:
                return invalid
            invalid = _bounded_positive_integer("forecast", MAX_FORECAST_MONTHS)
            if invalid is not None:
                return invalid

        return None

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        if response.mimetype == "text/html":
            body = response.get_data(as_text=True)
            body = body.replace(PLOTLY_CDN_TAG, PLOTLY_LOCAL_TAG)
            body = body.replace(HTMX_LEGACY_TAG, HTMX_PINNED_TAG)
            response.set_data(body)

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
