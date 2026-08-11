from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from src.interface_adapters.mcp_read_model import FinancialReadModel
from src.interface_adapters.official_apis import (
    BojTimeSeriesApiClient,
    EcbDataPortalApiClient,
    EStatApiV3Client,
    JQuantsApiV2Client,
    api_result_payload,
)
from src.interface_adapters.source_registry import external_data_source_status

MCP_SCHEMA_VERSION = "wealthaudit.mcp.v1"


def _repo_root() -> Path:
    configured = os.environ.get("WEALTHAUDIT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} is required for this external data source")
    return value


read_model = FinancialReadModel(_repo_root())
mcp = MCPServer(
    "WealthAudit",
    version="1.1.0",
    instructions=(
        "Local read-only household-finance MCP. Never infer missing values as zero, "
        "never expose absolute local paths or secrets, keep actual versus forecast explicit, "
        "and treat external APIs as provenance-bearing inputs rather than calculation engines."
    ),
)


@mcp.tool()
def get_financial_snapshot(period: str | None = None) -> dict[str, Any]:
    """Return one financial snapshot; without period, use the latest actual month."""
    return read_model.financial_snapshot(period=period)


@mcp.tool()
def get_balance_sheet(period: str | None = None) -> dict[str, Any]:
    """Return liquid, risk, pension and total financial assets for one period."""
    return read_model.balance_sheet(period=period)


@mcp.tool()
def get_cash_flow(period: str | None = None) -> dict[str, Any]:
    """Return income, expenditure, savings, contribution and reconciled wealth flow."""
    return read_model.cash_flow(period=period)


@mcp.tool()
def get_asset_allocation(period: str | None = None) -> dict[str, Any]:
    """Return allocation amounts and ratios using the dashboard's shared calculation path."""
    return read_model.asset_allocation(period=period)


@mcp.tool()
def get_investment_returns(period: str | None = None) -> dict[str, Any]:
    """Return materialized portfolio, benchmark and alpha return metrics."""
    return read_model.investment_returns(period=period)


@mcp.tool()
def get_fi_metrics(period: str | None = None) -> dict[str, Any]:
    """Return savings, risk-asset and financial-independence ratios."""
    return read_model.fi_metrics(period=period)


@mcp.tool()
def get_forecast(months: int = 12) -> dict[str, Any]:
    """Return up to 120 explicitly forecast rows plus materialized forecast assumptions."""
    return read_model.forecast(months=months)


@mcp.tool()
def get_warnings() -> dict[str, Any]:
    """Return fail-close warnings for missing, duplicate, stale or incomplete calculated data."""
    return read_model.warnings()


@mcp.tool()
def get_data_freshness() -> dict[str, Any]:
    """Return latest actual period, staleness, relative artifact identity and SHA-256."""
    return read_model.data_freshness()


@mcp.tool()
def get_audit_diff(limit: int = 100) -> dict[str, Any]:
    """Return bounded recalculation differences when the local audit has been materialized."""
    return read_model.audit_diff(limit=limit)


@mcp.tool()
def get_external_data_sources() -> dict[str, Any]:
    """List official API/MCP capabilities and configured-state booleans without secret values."""
    return external_data_source_status()


@mcp.tool()
def get_boj_time_series(parameters: dict[str, str]) -> dict[str, Any]:
    """Read a bounded response from the official BOJ Time-Series Data Search code API."""
    return api_result_payload(BojTimeSeriesApiClient().fetch(parameters))


@mcp.tool()
def get_ecb_series(
    flow_ref: str,
    key: str,
    parameters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read a bounded ECB Data Portal SDMX series response."""
    return api_result_payload(
        EcbDataPortalApiClient().fetch_series(flow_ref, key, parameters=parameters)
    )


@mcp.tool()
def get_estat_stats_data(
    stats_data_id: str,
    parameters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read e-Stat v3.0 statistics using ESTAT_APP_ID without exposing the application ID."""
    client = EStatApiV3Client(_required_env("ESTAT_APP_ID"))
    return api_result_payload(client.get_stats_data(stats_data_id, parameters=parameters))


@mcp.tool()
def get_jquants_daily_bars(
    code: str = "",
    date: str = "",
    from_date: str = "",
    to_date: str = "",
) -> dict[str, Any]:
    """Read J-Quants V2 daily equity bars using JQUANTS_API_KEY without exposing the key."""
    client = JQuantsApiV2Client(_required_env("JQUANTS_API_KEY"))
    return api_result_payload(
        client.get_daily_bars(
            code=code,
            date=date,
            from_date=from_date,
            to_date=to_date,
        )
    )


def main() -> None:
    """Serve only on loopback; remote binding is intentionally not configurable."""
    mcp.run("streamable-http", host="127.0.0.1", port=8012)


if __name__ == "__main__":
    main()
