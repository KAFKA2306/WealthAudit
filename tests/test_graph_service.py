import pandas as pd

from src.use_cases.graph_service import GraphService


def test_month_view_uses_last_completed_month_when_current_month_is_in_progress(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        "src.use_cases.graph_service.pd.Timestamp.now",
        lambda: pd.Timestamp("2026-08-02"),
    )
    data_dir = tmp_path
    calculated_dir = data_dir / "data" / "calculated"
    calculated_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "month": ["2025-08-31", "2026-07-31", "2026-08-31"],
            "liquid_assets": [1, 2, 3],
            "risk_assets": [4, 5, 6],
            "pension_assets": [7, 8, 9],
            "after_tax_income": [0, 0, 0],
            "expenditure": [0, 0, 0],
            "net_savings": [0, 0, 0],
            "investment_gain_loss": [0, 0, 0],
        }
    ).to_csv(calculated_dir / "forecast.csv", index=False)

    service = GraphService(data_dir=str(data_dir))
    filtered = service._filter_data(pd.read_csv(calculated_dir / "forecast.csv"), 12, None)

    assert list(filtered["month"]) == ["2025-08-31", "2026-07-31"]


def test_forecast_view_keeps_current_month_anchor(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "src.use_cases.graph_service.pd.Timestamp.now",
        lambda: pd.Timestamp("2026-08-02"),
    )
    data_dir = tmp_path
    calculated_dir = data_dir / "data" / "calculated"
    calculated_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "month": ["2025-08-31", "2026-07-31", "2026-08-31", "2026-09-30"],
            "liquid_assets": [1, 2, 3, 4],
            "risk_assets": [4, 5, 6, 7],
            "pension_assets": [7, 8, 9, 10],
            "after_tax_income": [0, 0, 0, 0],
            "expenditure": [0, 0, 0, 0],
            "net_savings": [0, 0, 0, 0],
            "investment_gain_loss": [0, 0, 0, 0],
        }
    ).to_csv(calculated_dir / "forecast.csv", index=False)

    service = GraphService(data_dir=str(data_dir))
    filtered = service._filter_data(pd.read_csv(calculated_dir / "forecast.csv"), None, 60)

    assert list(filtered["month"]) == [
        "2025-08-31",
        "2026-07-31",
        "2026-08-31",
        "2026-09-30",
    ]
