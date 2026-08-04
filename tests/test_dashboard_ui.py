from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.use_cases.graph_service import GraphService


class DashboardUiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        calculated = self.root / "data" / "calculated"
        calculated.mkdir(parents=True)
        rows = []
        for index, month in enumerate(("2025-01", "2025-02", "2025-03"), start=1):
            rows.append(
                {
                    "month": month,
                    "liquid_assets": 100 + index,
                    "risk_assets": 200 + index,
                    "pension_assets": 300 + index,
                    "after_tax_income": 40 + index,
                    "expenditure": 20 + index,
                    "investment_gain_loss": index,
                    "net_savings": 20,
                    "asset_contribution": 2,
                    "savings_rate": 0.3,
                    "risk_asset_ratio": 0.4,
                    "monthly_return": 0.01,
                    "benchmark_return": 0.008,
                    "monthly_alpha": 0.002,
                    "fi_ratio_12m": 2.0,
                    "fi_ratio_48m": 3.0,
                    "fi_ratio_next_12m": 3.5,
                }
            )
        pd.DataFrame(rows).to_csv(calculated / "forecast.csv", index=False)
        self.service = GraphService(str(self.root))

    def tearDown(self) -> None:
        self.temp.cleanup()

    @patch("src.use_cases.graph_service.last_completed_month", return_value="2025-02")
    def test_chart_includes_actual_forecast_boundary_and_table(self, _mock) -> None:
        output = self.service.get_net_worth_chart(forecast=12)
        self.assertIn("予測区間", output)
        self.assertIn("forecast-boundary", output)
        self.assertIn("同じデータを表で確認", output)
        self.assertIn("data-status-実績", output)
        self.assertIn("data-status-予測", output)
        self.assertIn("純資産合計", output)

    @patch("src.use_cases.graph_service.last_completed_month", return_value="2025-02")
    def test_dashboard_summary_uses_latest_completed_month(self, _mock) -> None:
        summary = self.service.dashboard_summary()
        self.assertEqual(summary["latest_month"], "2025-02")
        self.assertEqual(summary["net_worth"], "606万円")
        self.assertEqual(summary["cashflow"], "+24万円")
        self.assertEqual(summary["month_change"], "+3万円")

    def test_dashboard_template_has_decision_and_accessibility_contracts(self) -> None:
        template = (Path(__file__).parents[1] / "templates" / "dashboard.html").read_text(
            encoding="utf-8"
        )
        for marker in (
            'class="skip-link"',
            'id="current-status"',
            'id="warning-list"',
            'data-range="1y"',
            'data-range="forecast"',
            'id="forecast-note"',
            'data-route="net-worth"',
            'data-route="cashflow"',
            "new URLSearchParams(location.search)",
            "htmx:afterSwap",
            "prefers-reduced-motion",
        ):
            self.assertIn(marker, template)


if __name__ == "__main__":
    unittest.main()
