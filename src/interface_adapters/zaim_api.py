from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ZaimOAuthCredentials:
    consumer_key: str
    consumer_secret: str
    access_token: str
    access_token_secret: str


class ZaimApiError(RuntimeError):
    pass


def _percent(value: object) -> str:
    return quote(str(value), safe="~-._")


def oauth1_authorization_header(
    *,
    method: str,
    url: str,
    query: Mapping[str, object],
    credentials: ZaimOAuthCredentials,
    nonce: str | None = None,
    timestamp: int | None = None,
) -> str:
    split = urlsplit(url)
    base_url = urlunsplit((split.scheme, split.netloc, split.path, "", ""))
    oauth = {
        "oauth_consumer_key": credentials.consumer_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp if timestamp is not None else int(time.time())),
        "oauth_token": credentials.access_token,
        "oauth_version": "1.0",
    }

    pairs = list(parse_qsl(split.query, keep_blank_values=True))
    pairs.extend((str(key), str(value)) for key, value in query.items())
    pairs.extend(oauth.items())
    encoded_pairs = sorted((_percent(k), _percent(v)) for k, v in pairs)
    normalized = "&".join(f"{key}={value}" for key, value in encoded_pairs)
    base_string = "&".join(
        [_percent(method.upper()), _percent(base_url), _percent(normalized)]
    )
    signing_key = (
        f"{_percent(credentials.consumer_secret)}&"
        f"{_percent(credentials.access_token_secret)}"
    )
    digest = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    oauth["oauth_signature"] = base64.b64encode(digest).decode("ascii")
    return "OAuth " + ", ".join(
        f'{_percent(key)}="{_percent(value)}"' for key, value in sorted(oauth.items())
    )


class ZaimApiClient:
    MONEY_URL = "https://api.zaim.net/v2/home/money"

    def __init__(
        self,
        credentials: ZaimOAuthCredentials,
        *,
        opener: Callable[[Request, float], bytes] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.credentials = credentials
        self.opener = opener or _open_bytes
        self.timeout_seconds = timeout_seconds

    def get_money_page(
        self,
        *,
        page: int,
        limit: int = 100,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> bytes:
        params: dict[str, object] = {"page": page, "limit": limit}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        auth = oauth1_authorization_header(
            method="GET",
            url=self.MONEY_URL,
            query=params,
            credentials=self.credentials,
        )
        query = urlencode(params)
        request = Request(
            f"{self.MONEY_URL}?{query}",
            headers={
                "Authorization": auth,
                "Accept": "application/json",
                "User-Agent": "WealthAudit-Zaim-Probe/1",
            },
            method="GET",
        )
        return self.opener(request, self.timeout_seconds)

    def fetch_money_pages(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        max_pages: int = 1000,
    ) -> tuple[tuple[bytes, ...], tuple[Mapping[str, object], ...]]:
        pages: list[bytes] = []
        records: list[Mapping[str, object]] = []
        for page in range(1, max_pages + 1):
            raw = self.get_money_page(
                page=page,
                limit=limit,
                start_date=start_date,
                end_date=end_date,
            )
            pages.append(raw)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ZaimApiError("invalid JSON from Zaim API") from exc

            money = payload.get("money") if isinstance(payload, dict) else None
            if not isinstance(money, list):
                raise ZaimApiError("Zaim API response has no money list")
            records.extend(item for item in money if isinstance(item, dict))
            if len(money) < limit:
                break
        else:
            raise ZaimApiError("Zaim pagination exceeded max_pages")

        return tuple(pages), tuple(records)


def _open_bytes(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:
        return response.read()
