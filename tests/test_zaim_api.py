from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from src.interface_adapters.zaim_api import (
    ZaimApiClient,
    ZaimApiError,
    ZaimOAuthCredentials,
    oauth1_authorization_header,
)


def _credentials() -> ZaimOAuthCredentials:
    return ZaimOAuthCredentials(
        consumer_key="consumer-key",
        consumer_secret="consumer-secret",
        access_token="access-token",
        access_token_secret="access-token-secret",
    )


def test_oauth_header_is_deterministic_and_does_not_expose_secrets():
    first = oauth1_authorization_header(
        method="GET",
        url="https://api.zaim.net/v2/home/money",
        query={"page": 1, "limit": 100},
        credentials=_credentials(),
        nonce="fixed-nonce",
        timestamp=1_700_000_000,
    )
    second = oauth1_authorization_header(
        method="GET",
        url="https://api.zaim.net/v2/home/money",
        query={"page": 1, "limit": 100},
        credentials=_credentials(),
        nonce="fixed-nonce",
        timestamp=1_700_000_000,
    )
    assert first == second
    assert first.startswith("OAuth ")
    assert 'oauth_consumer_key="consumer-key"' in first
    assert 'oauth_token="access-token"' in first
    assert "oauth_signature=" in first
    assert "consumer-secret" not in first
    assert "access-token-secret" not in first


def test_fetch_money_pages_paginates_until_short_page():
    calls: list[int] = []

    def opener(request, timeout):
        assert timeout == 30.0
        query = parse_qs(urlsplit(request.full_url).query)
        page = int(query["page"][0])
        calls.append(page)
        if page == 1:
            return json.dumps(
                {
                    "money": [
                        {"id": 1, "date": "2026-09-20"},
                        {"id": 2, "date": "2026-09-21"},
                    ]
                }
            ).encode()
        return json.dumps(
            {"money": [{"id": 3, "date": "2026-09-22"}]}
        ).encode()

    client = ZaimApiClient(_credentials(), opener=opener)
    pages, records = client.fetch_money_pages(limit=2)

    assert calls == [1, 2]
    assert len(pages) == 2
    assert [item["id"] for item in records] == [1, 2, 3]


def test_fetch_money_pages_fails_closed_on_schema_change():
    client = ZaimApiClient(
        _credentials(),
        opener=lambda request, timeout: b'{"unexpected":[]}',
    )
    with pytest.raises(ZaimApiError, match="money list"):
        client.fetch_money_pages(limit=2)
