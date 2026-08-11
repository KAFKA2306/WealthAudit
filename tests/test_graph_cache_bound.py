from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.use_cases.graph_service import GraphService


def _write_forecast(root: Path) -> None:
    calculated = root / "data" / "calculated"
    calculated.mkdir(parents=True)
    pd.DataFrame(
        {
            "month": ["2026-01", "2026-02", "2026-03"],
            "liquid_assets": [100.0, 101.0, 102.0],
            "risk_assets": [200.0, 201.0, 202.0],
            "pension_assets": [50.0, 51.0, 52.0],
            "after_tax_income": [30.0, 30.0, 30.0],
            "expenditure": [20.0, 20.0, 20.0],
            "net_savings": [10.0, 10.0, 10.0],
            "investment_gain_loss": [1.0, 1.0, 1.0],
            "savings_rate": [0.3, 0.3, 0.3],
            "risk_asset_ratio": [0.5, 0.5, 0.5],
            "monthly_return": [0.01, 0.01, 0.01],
            "benchmark_return": [0.01, 0.01, 0.01],
            "monthly_alpha": [0.0, 0.0, 0.0],
            "fi_ratio_12m": [1.0, 1.0, 1.0],
            "fi_ratio_48m": [1.0, 1.0, 1.0],
            "fi_ratio_next_12m": [1.0, 1.0, 1.0],
        }
    ).to_csv(calculated / "forecast.csv", index=False)


def test_chart_cache_evicts_least_recently_used_entry(tmp_path: Path) -> None:
    _write_forecast(tmp_path)
    service = GraphService(data_dir=str(tmp_path), chart_cache_max_entries=2)

    service.get_net_worth_chart(months=1)
    first_key = next(iter(service._chart_cache))
    service.get_net_worth_chart(months=2)
    service.get_net_worth_chart(months=1)  # refresh first key as most recently used
    service.get_net_worth_chart(months=3)

    assert len(service._chart_cache) == 2
    assert first_key in service._chart_cache
    assert all(key[1] != 2 for key in service._chart_cache)


def test_chart_cache_limit_must_be_positive(tmp_path: Path) -> None:
    _write_forecast(tmp_path)
    with pytest.raises(ValueError, match="chart_cache_max_entries"):
        GraphService(data_dir=str(tmp_path), chart_cache_max_entries=0)
