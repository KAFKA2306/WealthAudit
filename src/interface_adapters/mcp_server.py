from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from src.interface_adapters.mcp_read_model import FinancialReadModel

MCP_SCHEMA_VERSION = "wealthaudit.mcp.v1"


def _repo_root() -> Path:
    configured = os.environ.get("WEALTHAUDIT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


read_model = FinancialReadModel(_repo_root())
mcp = MCPServer(
    "WealthAudit",
    version="1.0.0",
    instructions=(
        "Local read-only household-finance MCP. Never infer missing values as zero, "
        "never expose absolute local paths, and keep actual versus forecast explicit."
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


def main() -> None:
    """Serve only on loopback; remote binding is intentionally not configurable."""
    mcp.run("streamable-http", host="127.0.0.1", port=8012)


if __name__ == "__main__":
    main()
