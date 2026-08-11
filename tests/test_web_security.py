from __future__ import annotations

from src.infrastructure.web import create_app
from src.infrastructure.web_security import HTMX_INTEGRITY, HTMX_URL


def test_financial_routes_fail_closed_without_configured_access_token(monkeypatch) -> None:
    monkeypatch.delenv("WEALTHAUDIT_ACCESS_TOKEN", raising=False)
    response = create_app().test_client().get("/", headers={"Authorization": ""})

    assert response.status_code == 503
    assert "access token is not configured" in response.get_data(as_text=True)


def test_financial_routes_reject_unauthenticated_requests() -> None:
    response = create_app().test_client().get("/input", headers={"Authorization": ""})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic ")
    assert "月次入力" not in response.get_data(as_text=True)


def test_graph_query_parameters_are_bounded_before_data_access() -> None:
    client = create_app().test_client()

    assert client.get("/graphs/net-worth?months=-1").status_code == 400
    assert client.get("/graphs/net-worth?months=121").status_code == 400
    assert client.get("/graphs/net-worth?forecast=121").status_code == 400
    assert client.get("/graphs/net-worth?months=not-a-number").status_code == 400


def test_state_changing_requests_require_csrf_and_same_origin() -> None:
    client = create_app().test_client()

    bad_csrf = client.post("/input", data={"csrf_token": "wrong"})
    assert bad_csrf.status_code == 403

    cross_origin = client.post(
        "/input",
        data={"csrf_token": "test-csrf-token"},
        headers={"Origin": "https://example.invalid"},
    )
    assert cross_origin.status_code == 403


def test_security_headers_are_present_on_financial_responses() -> None:
    response = create_app().test_client().get("/input")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_dashboard_uses_local_plotly_and_sri_pinned_htmx() -> None:
    response = create_app().test_client().get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'src="/static/vendor/plotly.min.js"' in body
    assert "https://cdn.plot.ly" not in body
    assert f'src="{HTMX_URL}"' in body
    assert f'integrity="{HTMX_INTEGRITY}"' in body
    assert 'crossorigin="anonymous"' in body
    assert "https://unpkg.com" not in body

    csp = response.headers["Content-Security-Policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert "https://cdn.plot.ly" not in csp
    assert "https://unpkg.com" not in csp


def test_plotly_vendor_bundle_is_served_same_origin_without_financial_auth() -> None:
    response = create_app().test_client().get("/static/vendor/plotly.min.js")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert "Plotly" in response.get_data(as_text=True)[:2000]
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
