from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExternalDataSource:
    source_id: str
    name: str
    transport: str
    official_reference: str
    auth_env: str | None
    capabilities: tuple[str, ...]
    notes: str

    def status(self, environ: Mapping[str, str]) -> dict[str, object]:
        configured = self.auth_env is None or bool(environ.get(self.auth_env))
        payload = asdict(self)
        payload["configured"] = configured
        payload["auth_required"] = self.auth_env is not None
        payload["auth_env"] = self.auth_env
        return payload


EXTERNAL_DATA_SOURCES: tuple[ExternalDataSource, ...] = (
    ExternalDataSource(
        source_id="boj_time_series_api",
        name="BOJ Time-Series Data Search API",
        transport="https_api",
        official_reference="https://www.boj.or.jp/en/statistics/outline/notice_2026/not260218a.htm",
        auth_env=None,
        capabilities=("official_time_series", "fx", "interest_rates", "macro"),
        notes="Public API launched 2026-02-18; JSON/CSV time-series access.",
    ),
    ExternalDataSource(
        source_id="ecb_data_portal_api",
        name="ECB Data Portal API",
        transport="https_api",
        official_reference="https://data.ecb.europa.eu/help/api/overview",
        auth_env=None,
        capabilities=("official_time_series", "fx", "macro", "sdmx"),
        notes="SDMX 2.1 RESTful data and metadata service.",
    ),
    ExternalDataSource(
        source_id="estat_api_v3",
        name="e-Stat API v3.0",
        transport="https_api",
        official_reference="https://www.e-stat.go.jp/api/api-info/api-spec",
        auth_env="ESTAT_APP_ID",
        capabilities=("official_statistics", "cpi", "household", "labor"),
        notes="REST API; application ID is required by the official specification.",
    ),
    ExternalDataSource(
        source_id="jquants_api_v2",
        name="J-Quants API V2",
        transport="https_api",
        official_reference="https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260119.html",
        auth_env="JQUANTS_API_KEY",
        capabilities=("japan_equities", "prices", "financials", "listed_companies"),
        notes="API-key authenticated V2; use provider plan entitlements as the hard boundary.",
    ),
    ExternalDataSource(
        source_id="jquants_doc_mcp",
        name="J-Quants official documentation MCP",
        transport="mcp",
        official_reference="https://github.com/J-Quants/j-quants-doc-mcp",
        auth_env=None,
        capabilities=("api_documentation", "endpoint_discovery", "sample_code", "faq"),
        notes="Documentation MCP only; it is not a substitute for J-Quants market-data API calls.",
    ),
)


def external_data_source_status(
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    env = os.environ if environ is None else environ
    items = [source.status(env) for source in EXTERNAL_DATA_SOURCES]
    return {
        "schema_version": "wealthaudit.external-sources.v1",
        "count": len(items),
        "items": items,
    }
