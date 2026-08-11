from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


class OfficialApiError(RuntimeError):
    """Raised when an allow-listed official API request fails."""


@dataclass(frozen=True)
class ApiFetchResult:
    source_id: str
    request_url: str
    retrieved_at: str
    status: int
    content_type: str | None
    raw_sha256: str
    raw: bytes

    def json(self) -> Any:
        return json.loads(self.raw.decode("utf-8"))


MAX_RESPONSE_BYTES = 5_000_000

Opener = Callable[..., Any]


def api_result_payload(result: ApiFetchResult) -> dict[str, Any]:
    content_type = (result.content_type or "").lower()
    payload: dict[str, Any] = {
        "source_id": result.source_id,
        "request_url": result.request_url,
        "retrieved_at": result.retrieved_at,
        "status": result.status,
        "content_type": result.content_type,
        "raw_sha256": result.raw_sha256,
    }
    if "json" in content_type:
        payload["data"] = result.json()
    else:
        payload["data"] = result.raw.decode("utf-8", errors="replace")
    return payload


def _redact_query(url: str, secret_query_names: set[str]) -> str:
    if not secret_query_names:
        return url
    parsed = urlparse(url)
    pairs = [
        (key, "REDACTED" if key in secret_query_names else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunparse(parsed._replace(query=urlencode(pairs, doseq=True)))


def _fetch(
    *,
    source_id: str,
    url: str,
    allowed_host: str,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    secret_query_names: set[str] | None = None,
    opener: Opener = urlopen,
) -> ApiFetchResult:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != allowed_host:
        raise OfficialApiError(f"blocked non-official endpoint for {source_id}")

    request_headers = {
        "User-Agent": "WealthAudit/official-api-adapter",
        **dict(headers or {}),
    }
    request = Request(url, headers=request_headers, method="GET")
    try:
        response = opener(request, timeout=timeout)
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise OfficialApiError(f"{source_id} response exceeds size limit")
        status = int(getattr(response, "status", 200))
        content_type = None
        response_headers = getattr(response, "headers", None)
        if response_headers is not None:
            content_type = response_headers.get("Content-Type")
    except (HTTPError, URLError, OSError) as exc:
        raise OfficialApiError(f"{source_id} request failed") from exc

    return ApiFetchResult(
        source_id=source_id,
        request_url=_redact_query(url, secret_query_names or set()),
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        content_type=content_type,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw=raw,
    )


class BojTimeSeriesApiClient:
    """Thin client for the BOJ code API without embedding series semantics."""

    ENDPOINT = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"

    def fetch(self, parameters: Mapping[str, str], *, opener: Opener = urlopen) -> ApiFetchResult:
        query = urlencode(dict(parameters), doseq=True)
        return _fetch(
            source_id="boj_time_series_api",
            url=f"{self.ENDPOINT}?{query}" if query else self.ENDPOINT,
            allowed_host="www.stat-search.boj.or.jp",
            headers={"Accept": "application/json"},
            opener=opener,
        )


class EcbDataPortalApiClient:
    """Client for ECB Data Portal SDMX data queries."""

    BASE = "https://data-api.ecb.europa.eu/service/data"

    def fetch_series(
        self,
        flow_ref: str,
        key: str,
        *,
        parameters: Mapping[str, str] | None = None,
        opener: Opener = urlopen,
    ) -> ApiFetchResult:
        safe_flow = flow_ref.strip("/")
        safe_key = key.strip("/")
        if not safe_flow or not safe_key or "/" in safe_flow or "/" in safe_key:
            raise ValueError("flow_ref and key must be non-empty single path segments")
        query = urlencode(dict(parameters or {}), doseq=True)
        url = f"{self.BASE}/{safe_flow}/{safe_key}"
        if query:
            url = f"{url}?{query}"
        return _fetch(
            source_id="ecb_data_portal_api",
            url=url,
            allowed_host="data-api.ecb.europa.eu",
            headers={"Accept": "text/csv"},
            opener=opener,
        )


class EStatApiV3Client:
    """Client for the e-Stat v3.0 JSON getStatsData endpoint."""

    ENDPOINT = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

    def __init__(self, app_id: str) -> None:
        if not app_id:
            raise ValueError("e-Stat app_id is required")
        self._app_id = app_id

    def get_stats_data(
        self,
        stats_data_id: str,
        *,
        parameters: Mapping[str, str] | None = None,
        opener: Opener = urlopen,
    ) -> ApiFetchResult:
        if not stats_data_id:
            raise ValueError("stats_data_id is required")
        params = dict(parameters or {})
        params["appId"] = self._app_id
        params["statsDataId"] = stats_data_id
        return _fetch(
            source_id="estat_api_v3",
            url=f"{self.ENDPOINT}?{urlencode(params, doseq=True)}",
            allowed_host="api.e-stat.go.jp",
            headers={"Accept": "application/json"},
            secret_query_names={"appId"},
            opener=opener,
        )


class JQuantsApiV2Client:
    """Minimal J-Quants V2 daily-equity-bars client using x-api-key auth."""

    ENDPOINT = "https://api.jquants.com/v2/equities/bars/daily"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("J-Quants api_key is required")
        self._api_key = api_key

    def get_daily_bars(
        self,
        *,
        code: str = "",
        date: str = "",
        from_date: str = "",
        to_date: str = "",
        opener: Opener = urlopen,
    ) -> ApiFetchResult:
        params: dict[str, str] = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date
        else:
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
        query = urlencode(params)
        return _fetch(
            source_id="jquants_api_v2",
            url=f"{self.ENDPOINT}?{query}" if query else self.ENDPOINT,
            allowed_host="api.jquants.com",
            headers={"Accept": "application/json", "x-api-key": self._api_key},
            opener=opener,
        )
