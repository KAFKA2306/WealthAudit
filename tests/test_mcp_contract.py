from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd

from src.interface_adapters import mcp_server
from src.interface_adapters.mcp_read_model import FinancialReadModel
from src.use_cases.graph_service import last_completed_month


def write_dataset(root: Path) -> None:
    calculated = root / "data" / "calculated"
    calculated.mkdir(parents=True)
    cutoff = pd.Period(last_completed_month(), freq="M")
    rows = [
        {
            "month": str(cutoff - 1),
            "is_forecast": False,
            "liquid_assets": 100.0,
            "risk_assets": 200.0,
            "pension_assets": 50.0,
            "total_financial_assets": 350.0,
            "after_tax_income": 40.0,
            "expenditure": 25.0,
            "net_savings": 15.0,
            "asset_contribution": 2.0,
            "net_worth_contribution": 17.0,
            "investment_gain_loss": 3.0,
            "raw_monthly_return": 0.01,
            "monthly_return": 0.009,
            "raw_benchmark_return": 0.008,
            "benchmark_return": 0.007,
            "monthly_alpha": 0.002,
            "savings_rate": 0.375,
            "risk_asset_ratio": 0.7142857,
            "fi_ratio_12m": 0.12,
            "fi_ratio_48m": 0.10,
            "fi_ratio_next_12m": 0.8,
        },
        {
            "month": str(cutoff),
            "is_forecast": False,
            "liquid_assets": 110.0,
            "risk_assets": 210.0,
            "pension_assets": 55.0,
            "total_financial_assets": 375.0,
            "after_tax_income": 42.0,
            "expenditure": 26.0,
            "net_savings": 16.0,
            "asset_contribution": 2.0,
            "net_worth_contribution": 18.0,
            "investment_gain_loss": 7.0,
            "raw_monthly_return": 0.02,
            "monthly_return": 0.011,
            "raw_benchmark_return": 0.009,
            "benchmark_return": 0.008,
            "monthly_alpha": 0.003,
            "savings_rate": 0.38,
            "risk_asset_ratio": 0.7066667,
            "fi_ratio_12m": 0.15,
            "fi_ratio_48m": 0.11,
            "fi_ratio_next_12m": 0.82,
        },
        {
            "month": str(cutoff + 1),
            "is_forecast": True,
            "liquid_assets": 125.0,
            "risk_assets": 214.0,
            "pension_assets": 57.0,
            "total_financial_assets": 396.0,
            "after_tax_income": 42.0,
            "expenditure": 26.0,
            "net_savings": 16.0,
            "asset_contribution": 2.0,
            "net_worth_contribution": 18.0,
            "investment_gain_loss": 3.0,
            "raw_monthly_return": 0.01,
            "monthly_return": 0.01,
            "raw_benchmark_return": 0.008,
            "benchmark_return": 0.008,
            "monthly_alpha": 0.002,
            "savings_rate": 0.38,
            "risk_asset_ratio": 0.6843434,
            "fi_ratio_12m": 0.16,
            "fi_ratio_48m": 0.12,
            "fi_ratio_next_12m": 0.84,
        },
    ]
    pd.DataFrame(rows).to_csv(calculated / "forecast.csv", index=False)
    pd.DataFrame(
        [{"category": "Income", "item": "salary", "parameter": "annual_growth", "value": 0.03}]
    ).to_csv(calculated / "forecast_parameters.csv", index=False)
    pd.DataFrame(
        [{"file": "forecast.csv", "key": str(cutoff), "column": "risk_assets", "before": 209.0, "after": 210.0, "delta": 1.0}]
    ).to_csv(calculated / "recalculation_diff.csv", index=False)


def test_mcp_tool_catalog_is_discoverable() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "get_financial_snapshot",
        "get_balance_sheet",
        "get_cash_flow",
        "get_asset_allocation",
        "get_investment_returns",
        "get_fi_metrics",
        "get_forecast",
        "get_warnings",
        "get_data_freshness",
        "get_audit_diff",
    }


def test_latest_snapshot_is_actual_and_forecast_stays_explicit(tmp_path: Path) -> None:
    write_dataset(tmp_path)
    model = FinancialReadModel(tmp_path)
    snapshot = model.financial_snapshot()
    forecast = model.forecast(months=1)
    assert snapshot["available"] is True
    assert snapshot["actual_or_forecast"] == "actual"
    assert snapshot["period"] == last_completed_month()
    assert forecast["actual_or_forecast"] == "forecast"
    assert forecast["items"][0]["actual_or_forecast"] == "forecast"


def test_dashboard_and_mcp_allocation_use_same_calculation(tmp_path: Path) -> None:
    write_dataset(tmp_path)
    model = FinancialReadModel(tmp_path)
    payload = model.asset_allocation()
    values = payload["values"]
    total = values["liquid_assets"] + values["risk_assets"] + values["pension_assets"]
    assert values["liquid_assets_ratio"] == values["liquid_assets"] / total * 100
    assert values["risk_assets_ratio"] == values["risk_assets"] / total * 100
    assert values["pension_assets_ratio"] == values["pension_assets"] / total * 100


def test_private_absolute_path_never_appears_in_provenance(tmp_path: Path) -> None:
    write_dataset(tmp_path)
    model = FinancialReadModel(tmp_path)
    payloads = [
        model.financial_snapshot(),
        model.data_freshness(),
        model.audit_diff(),
        model.forecast(months=1),
    ]
    serialized = repr(payloads)
    assert str(tmp_path) not in serialized
    assert "data/calculated/forecast.csv" in serialized


def test_missing_values_are_null_not_zero(tmp_path: Path) -> None:
    write_dataset(tmp_path)
    path = tmp_path / "data" / "calculated" / "forecast.csv"
    frame = pd.read_csv(path)
    frame.loc[1, "monthly_alpha"] = float("nan")
    frame.to_csv(path, index=False)
    model = FinancialReadModel(tmp_path)
    result = model.investment_returns()
    assert result["values"]["monthly_alpha"] is None
    assert result["null_reasons"]["monthly_alpha"] == "value_missing"


def test_warnings_and_freshness_are_fail_close(tmp_path: Path) -> None:
    model = FinancialReadModel(tmp_path)
    assert model.warnings()["status"] == "unavailable"
    freshness = model.data_freshness()
    assert freshness["available"] is False
    assert freshness["null_reason"] == "artifact_not_materialized"


def test_recalculation_diff_and_hash_provenance(tmp_path: Path) -> None:
    write_dataset(tmp_path)
    model = FinancialReadModel(tmp_path)
    diff = model.audit_diff(limit=1)
    freshness = model.data_freshness()
    assert diff["available"] is True
    assert diff["count"] == 1
    assert len(diff["provenance"]["input_hash"]) == 64
    assert freshness["stale"] is False
    assert freshness["edinetdb_mode"] == "not_applicable"
    assert len(freshness["input_hash"]) == 64


def test_server_is_hardcoded_to_loopback() -> None:
    source = (Path(__file__).resolve().parents[1] / "src" / "interface_adapters" / "mcp_server.py").read_text(encoding="utf-8")
    assert 'host="127.0.0.1"' in source
    assert "0.0.0.0" not in source
