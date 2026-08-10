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


_CI_ACCOUNTS = """account_id,name,type,currency,risk
yucho,Sample bank 01,bank,JPY,0
sony,Sample bank 02,bank,JPY,0
deutsche,Sample bank 03,bank,JPY,0
minna,Sample bank 04,bank,JPY,0
jonan,Sample bank 05,bank,JPY,0
wise,Sample fintech 01,fintech,multi,0
sbi_sec,Sample securities 01,securities,JPY,1
rakuten_sec,Sample securities 02,securities,JPY,1
monex_sec,Sample securities 03,securities,JPY,1
binance,Sample crypto 01,crypto,multi,1
kosei_nenkin,Sample pension 01,pension,JPY,0
dc,Sample pension 02,pension,JPY,1
rakuten,Sample bank 06,bank,JPY,0
"""

_CI_PAYMENT_METHODS = """method_id,name,settlement_day,settlement_account
smbc_numberless,Sample card 01,26,rakuten_sec
smbc_amazon,Sample card 02,26,sony
rakuten_jcb,Sample card 03,27,rakuten_sec
rakuten_mastercard,Sample card 04,27,rakuten_sec
epos,Sample card 05,27,yucho
monex_card,Sample card 06,27,rakuten_sec
sony_card,Sample debit 01,0,sony
mercari,Sample card 07,27,sony
wise,Sample transfer 01,0,wise
cash,Sample cash payment,0,
adjustment,Sample adjustment,0,
"""


@pytest.fixture(scope="session", autouse=True)
def bootstrap_ci_private_masters() -> None:
    """Seed ignored synthetic masters in CI without publishing display metadata."""

    if os.environ.get("CI", "").lower() != "true":
        yield
        return

    created: list[Path] = []
    for private_name, content in (
        ("accounts.csv", _CI_ACCOUNTS),
        ("payment_methods.csv", _CI_PAYMENT_METHODS),
    ):
        destination = ROOT / "master" / private_name
        if destination.exists():
            raise RuntimeError(f"CI checkout unexpectedly contains private master: {destination}")
        destination.write_text(content, encoding="utf-8")
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
