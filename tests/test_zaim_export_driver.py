from __future__ import annotations

import json

from scripts.provider_drivers import zaim_export


def test_missing_zaim_credentials_returns_auth_required(monkeypatch, capsys):
    for name in (
        "ZAIM_CONSUMER_KEY",
        "ZAIM_CONSUMER_SECRET",
        "ZAIM_ACCESS_TOKEN",
        "ZAIM_ACCESS_TOKEN_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    result = zaim_export.main()
    payload = json.loads(capsys.readouterr().out)

    assert result == 20
    assert payload == {
        "status": "AUTH_REQUIRED",
        "error_code": "ZAIM_OAUTH_CREDENTIALS_REQUIRED",
    }
