from __future__ import annotations

import base64
import os
from pathlib import Path
import sys
from typing import Any

import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers, MultiDict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def secure_web_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep legacy web tests explicit about the new authenticated boundary."""

    monkeypatch.setenv("WEALTHAUDIT_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setenv("WEALTHAUDIT_CSRF_TOKEN", "test-csrf-token")

    original_open = FlaskClient.open
    credentials = base64.b64encode(b"wealthaudit:test-access-token").decode("ascii")

    def authenticated_open(self: FlaskClient, *args: Any, **kwargs: Any):
        headers = Headers(kwargs.pop("headers", None))
        if "Authorization" not in headers:
            headers["Authorization"] = f"Basic {credentials}"
        kwargs["headers"] = headers

        method = str(kwargs.get("method", "GET")).upper()
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            data = kwargs.get("data")
            if isinstance(data, dict):
                patched = dict(data)
                patched.setdefault("csrf_token", "test-csrf-token")
                kwargs["data"] = patched
            elif isinstance(data, MultiDict):
                patched_multi = data.copy()
                if "csrf_token" not in patched_multi:
                    patched_multi.add("csrf_token", "test-csrf-token")
                kwargs["data"] = patched_multi

        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(FlaskClient, "open", authenticated_open)
