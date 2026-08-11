from __future__ import annotations

from email.message import Message

from src.interface_adapters.official_apis import (
    BojTimeSeriesApiClient,
    EcbDataPortalApiClient,
    EStatApiV3Client,
    JQuantsApiV2Client,
)
from src.interface_adapters.source_registry import external_data_source_status


class _Response:
    status = 200

    def __init__(self, raw: bytes = b'{"ok": true}') -> None:
        self._raw = raw
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self._raw
        return self._raw[:size]


def _recording_opener(calls: list):
    def opener(request, timeout=0):
        calls.append((request, timeout))
        return _Response()

    return opener


def test_source_registry_never_exposes_secret_values():
    status = external_data_source_status(
        {"ESTAT_APP_ID": "estat-secret", "JQUANTS_API_KEY": "jq-secret"}
    )
    serialized = repr(status)
    assert "estat-secret" not in serialized
    assert "jq-secret" not in serialized
    configured = {item["source_id"]: item["configured"] for item in status["items"]}
    assert configured["estat_api_v3"] is True
    assert configured["jquants_api_v2"] is True


def test_boj_client_is_pinned_to_official_https_host():
    calls = []
    result = BojTimeSeriesApiClient().fetch(
        {"db": "TEST", "code": "SERIES"}, opener=_recording_opener(calls)
    )
    assert calls[0][0].full_url.startswith(
        "https://www.stat-search.boj.or.jp/api/v1/getDataCode?"
    )
    assert result.source_id == "boj_time_series_api"
    assert len(result.raw_sha256) == 64


def test_ecb_client_uses_sdmx_data_endpoint_and_csv_accept():
    calls = []
    EcbDataPortalApiClient().fetch_series(
        "EXR",
        "M.USD.EUR.SP00.A",
        parameters={"startPeriod": "2026-01"},
        opener=_recording_opener(calls),
    )
    request = calls[0][0]
    assert request.full_url.startswith(
        "https://data-api.ecb.europa.eu/service/data/EXR/M.USD.EUR.SP00.A?"
    )
    assert request.get_header("Accept") == "text/csv"


def test_estat_app_id_is_sent_but_redacted_from_provenance_url():
    calls = []
    result = EStatApiV3Client("estat-secret").get_stats_data(
        "00000000", opener=_recording_opener(calls)
    )
    assert "appId=estat-secret" in calls[0][0].full_url
    assert "estat-secret" not in result.request_url
    assert "appId=REDACTED" in result.request_url


def test_jquants_api_key_stays_in_header_and_out_of_url():
    calls = []
    result = JQuantsApiV2Client("jq-secret").get_daily_bars(
        code="7203", date="20260810", opener=_recording_opener(calls)
    )
    request = calls[0][0]
    assert request.full_url.startswith(
        "https://api.jquants.com/v2/equities/bars/daily?"
    )
    assert "jq-secret" not in request.full_url
    assert request.get_header("X-api-key") == "jq-secret"
    assert "jq-secret" not in result.request_url
