from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from scripts.forecast import (
    annual_to_monthly_rate,
    calculate_metrics_vectorized,
    export_annual_summary,
    forecast_expense,
    forecast_salary_income,
)
from src.constants import AccountId, AccountType, AssetClassId, Currency
from src.domain.entities.models import Account, Asset, AssetClass, Market, Month
from src.use_cases.calculators.balance_sheet import BalanceSheetCalculator
from src.use_cases.calculators.metrics import MetricsCalculator
from src.use_cases.dtos.output import BalanceSheet, CashFlowStatement
from src.use_cases.graph_service import total_wealth_flow
from src.use_cases.valuation import value_asset


def account(
    account_id: AccountId,
    currency: Currency,
    *,
    account_type: AccountType = AccountType.BANK,
    risk: int = 0,
) -> Account:
    return Account(account_id, account_id.value, account_type, currency, risk)


def market(month: str, usd: float = 150.0, eur: float = 160.0) -> Market:
    return Market(Month(month), usd, eur, 5000.0)


def test_jpy_and_usd_assets_reconcile_to_jpy() -> None:
    accounts = [
        account(AccountId.YUCHO, Currency.JPY),
        account(
            AccountId.SBI_SEC,
            Currency.USD,
            account_type=AccountType.SECURITIES,
            risk=1,
        ),
    ]
    assets = [
        Asset(
            Month("2026-01"),
            AccountId.YUCHO,
            AssetClassId.CASH,
            balance=1_000_000,
        ),
        Asset(
            Month("2026-01"),
            AccountId.SBI_SEC,
            AssetClassId.STOCK_US,
            balance=10_000,
        ),
    ]
    classes = [
        AssetClass(AssetClassId.CASH, "cash", 0),
        AssetClass(AssetClassId.STOCK_US, "stock", 1),
    ]

    result = BalanceSheetCalculator().calculate(
        assets, [market("2026-01")], accounts, [], classes
    )[0]

    assert result.liquid_assets == 1_000_000
    assert result.risk_assets == 1_500_000
    assert result.total_financial_assets == 2_500_000


def test_multi_currency_account_uses_row_currency() -> None:
    wise = account(AccountId.WISE, Currency.MULTI)
    asset = Asset(
        Month("2026-01"),
        AccountId.WISE,
        AssetClassId.CASH,
        native_balance=100,
        native_currency=Currency.EUR,
    )

    valuation = value_asset(asset, wise, [market("2026-01", eur=160)])

    assert valuation.jpy_value == 16_000


def test_multi_currency_account_requires_row_currency() -> None:
    wise = account(AccountId.WISE, Currency.MULTI)
    asset = Asset(
        Month("2026-01"), AccountId.WISE, AssetClassId.CASH, balance=100
    )

    with pytest.raises(ValueError, match="requires native_currency"):
        value_asset(asset, wise, [market("2026-01")])


def test_valuation_never_uses_future_market_data() -> None:
    usd_account = account(AccountId.SBI_SEC, Currency.USD, risk=1)
    asset = Asset(
        Month("2026-01"),
        AccountId.SBI_SEC,
        AssetClassId.STOCK_US,
        balance=100,
    )

    with pytest.raises(ValueError, match="Market data is required to convert USD asset"):
        value_asset(asset, usd_account, [market("2026-02")])


def test_return_denominator_includes_pension_and_excludes_contribution() -> None:
    accounts = [
        account(
            AccountId.SBI_SEC,
            Currency.JPY,
            account_type=AccountType.SECURITIES,
            risk=1,
        ),
        account(
            AccountId.DC,
            Currency.JPY,
            account_type=AccountType.PENSION,
            risk=1,
        ),
    ]
    classes = [
        AssetClass(AssetClassId.FUND, "fund", 1),
        AssetClass(AssetClassId.PENSION, "pension", 1),
    ]
    assets = [
        Asset(
            Month("2026-01"),
            AccountId.SBI_SEC,
            AssetClassId.FUND,
            balance=1_000_000,
        ),
        Asset(
            Month("2026-01"),
            AccountId.DC,
            AssetClassId.PENSION,
            balance=9_000_000,
        ),
        Asset(
            Month("2026-02"),
            AccountId.SBI_SEC,
            AssetClassId.FUND,
            balance=1_000_000,
        ),
        Asset(
            Month("2026-02"),
            AccountId.DC,
            AssetClassId.PENSION,
            balance=10_000_000,
        ),
    ]
    cashflows = [
        CashFlowStatement(Month("2026-01"), 0, 0, 0),
        CashFlowStatement(
            Month("2026-02"), 0, 0, 0, asset_contribution=100_000
        ),
    ]

    balance_sheets = BalanceSheetCalculator().calculate(
        assets, [], accounts, cashflows, classes
    )
    metrics = MetricsCalculator().calculate(cashflows, balance_sheets, [])

    assert balance_sheets[1].investment_gain_loss == 900_000
    assert balance_sheets[1].return_base_assets == 10_000_000
    assert metrics[1].raw_monthly_return == pytest.approx(0.09)


def test_gap_in_calendar_months_does_not_create_one_month_return() -> None:
    cashflows = [
        CashFlowStatement(Month("2026-01"), 0, 0, 0),
        CashFlowStatement(Month("2026-03"), 0, 0, 0),
    ]
    balances = [
        BalanceSheet(Month("2026-01"), 0, 100, 0, 100, 0, 0),
        BalanceSheet(Month("2026-03"), 0, 110, 0, 110, 0, 0),
    ]

    result = MetricsCalculator().calculate(cashflows, balances, [])

    assert math.isnan(result[1].raw_monthly_return)


def test_annual_rate_conversion_is_effective_not_divided_by_twelve() -> None:
    monthly = annual_to_monthly_rate(0.05)

    assert monthly == pytest.approx((1.05 ** (1 / 12)) - 1)
    assert (1 + monthly) ** 12 - 1 == pytest.approx(0.05)


def test_salary_growth_waits_for_actual_raise_boundary() -> None:
    months = pd.date_range("2025-01-01", "2026-02-01", freq="MS")
    values = [100.0 if date.year == 2025 else 110.0 for date in months]
    history = pd.DataFrame({"month": months.strftime("%Y-%m"), "salary": values})

    forecast = forecast_salary_income(history, "salary", ["2026-03", "2026-04"])

    assert forecast["2026-04"] / forecast["2026-03"] == pytest.approx(1.1)


def test_variable_expense_trend_compounds_each_forecast_year() -> None:
    months = pd.date_range("2024-01-01", "2025-12-01", freq="MS")
    values = [100.0] * 21 + [200.0, 200.0, 200.0]
    history = pd.DataFrame({"month": months.strftime("%Y-%m"), "expense": values})

    forecast = forecast_expense(history, "expense", ["2026-01", "2027-01"])

    assert forecast["2027-01"] > forecast["2026-01"]


def test_annual_summary_links_raw_returns_not_smoothed_returns(
    tmp_path: Path,
) -> None:
    frame = pd.DataFrame(
        {
            "month": ["2026-01", "2026-02"],
            "raw_monthly_return": [0.10, -0.10],
            "monthly_return": [0.10, 0.10],
            "raw_benchmark_return": [0.0, 0.0],
            "after_tax_income": [0.0, 0.0],
            "expenditure": [0.0, 0.0],
            "net_savings": [0.0, 0.0],
            "investment_gain_loss": [0.0, 0.0],
            "liquid_assets": [0.0, 0.0],
            "risk_assets": [100.0, 99.0],
            "pension_assets": [0.0, 0.0],
            "total_financial_assets": [100.0, 99.0],
            "return_base_assets": [0.0, 100.0],
        }
    )

    annual = export_annual_summary(frame, tmp_path)

    assert annual.loc[0, "annual_return"] == pytest.approx((1.1 * 0.9) - 1)
    assert annual.loc[0, "annual_return"] != pytest.approx((1.1 * 1.1) - 1)


def test_forecast_alpha_is_undefined_without_benchmark_assumption() -> None:
    frame = pd.DataFrame(
        {
            "month": ["2026-01", "2026-02"],
            "is_forecast": [False, True],
            "liquid_assets": [0.0, 0.0],
            "risk_assets": [100.0, 101.0],
            "pension_assets": [0.0, 0.0],
            "total_financial_assets": [100.0, 101.0],
            "investment_gain_loss": [0.0, 1.0],
            "return_base_assets": [0.0, 100.0],
            "after_tax_income": [0.0, 0.0],
            "expenditure": [1.0, 1.0],
            "net_savings": [0.0, 0.0],
            "raw_benchmark_return": [0.01, math.nan],
        }
    )

    result = calculate_metrics_vectorized(
        frame,
        portfolio_expected_monthly_return=0.02,
        benchmark_expected_monthly_return=None,
    )

    assert math.isnan(result.loc[1, "benchmark_return"])
    assert math.isnan(result.loc[1, "monthly_alpha"])


def test_total_flow_includes_asset_contribution() -> None:
    frame = pd.DataFrame(
        {
            "net_savings": [10.0],
            "asset_contribution": [5.0],
            "net_worth_contribution": [15.0],
            "investment_gain_loss": [2.0],
        }
    )

    assert total_wealth_flow(frame).iloc[0] == 17.0


def test_web_accepts_native_currency_for_multi_account(
    tmp_path: Path, monkeypatch
) -> None:
    pytest.importorskip("flask")
    from src.infrastructure.web import create_app

    monkeypatch.chdir(tmp_path)
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "input.html").write_text(
        (Path(__file__).parents[1] / "templates" / "input.html").read_text()
    )
    (tmp_path / "templates" / "dashboard.html").write_text("dashboard")
    (tmp_path / "data" / "input").mkdir(parents=True)
    (tmp_path / "data" / "calculated").mkdir(parents=True)
    (tmp_path / "master").mkdir()
    pd.DataFrame(
        [
            {
                "account_id": "wise",
                "name": "WISE",
                "type": "fintech",
                "currency": "multi",
                "risk": 0,
            }
        ]
    ).to_csv(tmp_path / "master" / "accounts.csv", index=False)
    pd.DataFrame(
        [{"method_id": "cash", "name": "Cash", "settlement_day": 0}]
    ).to_csv(tmp_path / "master" / "payment_methods.csv", index=False)
    pd.DataFrame(columns=["month", "account_id", "amount"]).to_csv(
        tmp_path / "data" / "input" / "income.csv", index=False
    )
    pd.DataFrame(columns=["month", "method_id", "amount"]).to_csv(
        tmp_path / "data" / "input" / "expense.csv", index=False
    )
    pd.DataFrame(
        columns=["month", "account_id", "asset_class", "balance"]
    ).to_csv(tmp_path / "data" / "input" / "assets.csv", index=False)
    monkeypatch.setattr(
        "src.infrastructure.web.subprocess.run", lambda *args, **kwargs: None
    )

    response = create_app().test_client().post(
        "/input",
        data={
            "target_month": "2026-08",
            "asset_account[]": ["wise"],
            "asset_class[]": ["cash"],
            "asset_currency[]": ["EUR"],
            "asset_balance[]": ["100"],
        },
    )

    assert response.status_code == 302
    stored = pd.read_csv(tmp_path / "data" / "input" / "assets.csv")
    assert stored.loc[0, "native_currency"] == "EUR"
    assert stored.loc[0, "balance"] == 100
