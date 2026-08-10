from __future__ import annotations

import base64
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers, MultiDict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def bootstrap_ci_private_masters() -> None:
    """Seed ignored synthetic masters in CI without publishing user metadata."""

    if os.environ.get("CI", "").lower() != "true":
        yield
        return

    created: list[Path] = []
    for source_name, private_name in (
        ("accounts.example.csv", "accounts.csv"),
        ("payment_methods.example.csv", "payment_methods.csv"),
    ):
        source = ROOT / "master" / source_name
        destination = ROOT / "master" / private_name
        if destination.exists():
            raise RuntimeError(f"CI checkout unexpectedly contains private master: {destination}")
        shutil.copyfile(source, destination)
        created.append(destination)

    try:
        yield
    finally:
        for path in created:
            path.unlink(missing_ok=True)


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
