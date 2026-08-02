import pandas as pd

from scripts.forecast import (
    calculate_bs_derived,
    export_annual_summary,
    forecast_income_by_stream,
    stream_kind_totals,
)


def test_pension_and_dc_streams_are_asset_contributions_not_cash_income() -> None:
    accounts = pd.DataFrame(
        [
            {
                "account_id": "kosei_nenkin",
                "name": "厚生年金",
                "type": "pension",
                "risk": 0,
            },
            {
                "account_id": "dc",
                "name": "確定拠出年金",
                "type": "pension",
                "risk": 1,
            },
        ]
    )
    streams = pd.DataFrame(
        [
            {
                "stream_id": "kosei_nenkin_contrib",
                "display_name": "厚生年金拠出",
                "kind": "asset_contribution",
                "source_account_ids": "kosei_nenkin",
                "forecast_to_account_id": "kosei_nenkin",
            },
            {
                "stream_id": "dc_contrib",
                "display_name": "確定拠出年金拠出",
                "kind": "asset_contribution",
                "source_account_ids": "dc",
                "forecast_to_account_id": "dc",
            },
        ]
    )
    history = pd.DataFrame(
        {
            "month": ["2026-06"],
            "収入_厚生年金": [30000],
            "収入_確定拠出年金": [25000],
        }
    )

    forecast_income, stream_amounts = forecast_income_by_stream(
        history,
        ["収入_厚生年金", "収入_確定拠出年金"],
        ["2026-07"],
        accounts,
        streams,
    )
    kind_totals = stream_kind_totals(stream_amounts, streams)

    assert forecast_income.loc["2026-07", "収入_厚生年金"] == 30000
    assert forecast_income.loc["2026-07", "収入_確定拠出年金"] == 25000
    assert kind_totals["asset_contribution"].loc["2026-07"] == 55000
    assert kind_totals["cash_income"].loc["2026-07"] == 0


def test_investment_gain_loss_subtracts_net_worth_contribution() -> None:
    df = pd.DataFrame(
        {
            "month": ["2026-06", "2026-07"],
            "liquid_assets": [100.0, 100.0],
            "risk_assets": [200.0, 200.0],
            "pension_assets": [700.0, 730.0],
            "net_savings": [0.0, 10.0],
            "net_worth_contribution": [0.0, 30.0],
        }
    )

    result = calculate_bs_derived(df)

    assert result.loc[1, "total_financial_assets"] == 1030.0
    assert result.loc[1, "investment_gain_loss"] == 0.0


def test_calculate_bs_derived_falls_back_to_cash_and_asset_contribution() -> None:
    df = pd.DataFrame(
        {
            "month": ["2026-06", "2026-07"],
            "liquid_assets": [100.0, 100.0],
            "risk_assets": [200.0, 200.0],
            "pension_assets": [700.0, 740.0],
            "cash_savings": [0.0, 10.0],
            "asset_contribution": [0.0, 30.0],
        }
    )

    result = calculate_bs_derived(df)

    assert result.loc[1, "total_financial_assets"] == 1040.0
    assert result.loc[1, "investment_gain_loss"] == 0.0


def test_export_annual_summary_compounds_raw_monthly_returns(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "month": ["2025-12", "2026-01", "2026-02"],
            "cash_income": [0.0, 0.0, 0.0],
            "asset_contribution": [0.0, 0.0, 0.0],
            "cash_savings": [0.0, 0.0, 0.0],
            "net_worth_contribution": [0.0, 0.0, 0.0],
            "after_tax_income": [0.0, 0.0, 0.0],
            "expenditure": [0.0, 0.0, 0.0],
            "net_savings": [0.0, 0.0, 0.0],
            "liquid_assets": [0.0, 0.0, 0.0],
            "risk_assets": [100.0, 110.0, 121.0],
            "pension_assets": [0.0, 0.0, 0.0],
            "total_financial_assets": [100.0, 110.0, 121.0],
            "investment_gain_loss": [0.0, 10.0, 11.0],
            "monthly_return": [0.99, 0.5, 0.25],
        }
    )

    export_annual_summary(df, tmp_path)
    annual = pd.read_csv(tmp_path / "forecast_annual.csv")
    annual_2026 = annual[annual["year"] == 2026].iloc[0]

    assert annual_2026["annual_return"] == 0.21
