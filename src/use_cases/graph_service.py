from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, cast

import pandas as pd
import plotly.graph_objects as go

CHART_COLORS = {
    "navy": "#17233f",
    "ink": "#13233f",
    "muted": "#788291",
    "gold": "#c99a3a",
    "sage": "#738b73",
    "rose": "#b87460",
    "slate": "#7d8998",
}


def total_wealth_flow(df: pd.DataFrame) -> pd.Series:
    """Return the flow that exactly reconciles the change in net worth."""
    contribution = (
        df["net_worth_contribution"]
        if "net_worth_contribution" in df
        else df["net_savings"]
        + df.get("asset_contribution", pd.Series(0.0, index=df.index))
    )
    return contribution + df["investment_gain_loss"]


@dataclass
class GraphService:
    data_dir: str
    _csv_cache: dict[str, tuple[float, pd.DataFrame]] = field(default_factory=dict)
    _chart_cache: dict[tuple[str, Optional[int], Optional[int], float], str] = field(
        default_factory=dict
    )

    def warm_visible_cache(self) -> None:
        ranges = (
            {"months": 12, "forecast": None},
            {"months": None, "forecast": None},
            {"months": None, "forecast": 60},
        )
        builders: tuple[Callable[..., str], ...] = (
            self.get_net_worth_chart,
            self.get_cashflow_chart,
            self.get_allocation_chart,
            self.get_ratios_chart,
            self.get_returns_chart,
            self.get_fi_chart,
        )
        for range_args in ranges:
            for builder in builders:
                builder(**range_args)

    def clear_cache(self) -> None:
        self._csv_cache.clear()
        self._chart_cache.clear()

    def _csv_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, "data", "calculated", filename)

    def _cache_key(
        self, name: str, months: Optional[int], forecast: Optional[int]
    ) -> tuple[str, Optional[int], Optional[int], float]:
        return (name, months, forecast, os.path.getmtime(self._csv_path("forecast.csv")))

    def _load_csv(self, filename: str) -> pd.DataFrame:
        path = self._csv_path(filename)
        mtime = os.path.getmtime(path)
        cached = self._csv_cache.get(filename)
        if cached and cached[0] == mtime:
            return cached[1]
        frame = pd.read_csv(path)
        self._csv_cache[filename] = (mtime, frame)
        return frame

    def _data(self, months: Optional[int], forecast: Optional[int]) -> pd.DataFrame:
        frame = self._load_csv("forecast.csv")
        current = datetime.now().strftime("%Y-%m")
        if forecast:
            start = (pd.to_datetime(current) - pd.DateOffset(months=12)).strftime("%Y-%m")
            end = (pd.to_datetime(current) + pd.DateOffset(months=forecast)).strftime("%Y-%m")
            return frame[(frame["month"] >= start) & (frame["month"] <= end)]
        actual = frame[frame["month"] <= current]
        return actual.tail(months) if months else actual

    def _to_html(self, figure: go.Figure) -> str:
        figure.update_layout(
            font=dict(family="Manrope, Arial, sans-serif", color=CHART_COLORS["ink"]),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,255,255,0)",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="right",
                x=1,
                font=dict(color=CHART_COLORS["muted"], size=12),
            ),
        )
        return cast(
            str,
            figure.to_html(
                full_html=False,
                include_plotlyjs=False,
                default_width="100%",
                config={"displayModeBar": False, "responsive": True},
            ),
        )

    def _cached(
        self,
        name: str,
        months: Optional[int],
        forecast: Optional[int],
        builder: Callable[[pd.DataFrame], go.Figure],
    ) -> str:
        key = self._cache_key(name, months, forecast)
        if key not in self._chart_cache:
            self._chart_cache[key] = self._to_html(builder(self._data(months, forecast)))
        return self._chart_cache[key]

    def get_net_worth_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        def build(df: pd.DataFrame) -> go.Figure:
            figure = go.Figure()
            for column, name, color in (
                ("liquid_assets", "Liquid Assets", CHART_COLORS["navy"]),
                ("risk_assets", "Risk Assets", CHART_COLORS["gold"]),
                ("pension_assets", "Pension Assets", CHART_COLORS["sage"]),
            ):
                figure.add_bar(x=df["month"], y=df[column], name=name, marker_color=color)
            figure.update_layout(
                title="Net Worth Trend (万円)", barmode="stack", yaxis_title="Amount (万円)"
            )
            return figure

        return self._cached("net_worth", months, forecast, build)

    def get_cashflow_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        def build(df: pd.DataFrame) -> go.Figure:
            figure = go.Figure()
            figure.add_bar(
                x=df["month"],
                y=df["after_tax_income"],
                name="Income",
                marker_color=CHART_COLORS["sage"],
            )
            figure.add_bar(
                x=df["month"],
                y=-df["expenditure"],
                name="Expenses",
                marker_color=CHART_COLORS["rose"],
            )
            figure.add_bar(
                x=df["month"],
                y=df["investment_gain_loss"],
                name="Investment G/L",
                marker_color=CHART_COLORS["gold"],
            )
            flow = total_wealth_flow(df)
            figure.add_scatter(
                x=df["month"],
                y=flow,
                name="Total Wealth Flow",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["navy"], width=3),
            )
            figure.add_scatter(
                x=df["month"],
                y=flow.rolling(12, min_periods=1).mean(),
                name="Total Wealth Flow (12MA)",
                mode="lines",
                line=dict(color=CHART_COLORS["gold"], width=3, dash="dash"),
            )
            figure.update_layout(
                title="Monthly Cash Flow (万円)",
                barmode="relative",
                yaxis_title="Amount (万円)",
            )
            return figure

        return self._cached("cashflow", months, forecast, build)

    def get_allocation_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        def build(df: pd.DataFrame) -> go.Figure:
            total = df[["liquid_assets", "risk_assets", "pension_assets"]].sum(axis=1)
            denominator = total.where(total != 0)
            figure = go.Figure()
            for column, name, color in (
                ("liquid_assets", "Liquid Assets", CHART_COLORS["navy"]),
                ("risk_assets", "Risk Assets", CHART_COLORS["gold"]),
                ("pension_assets", "Pension Assets", CHART_COLORS["sage"]),
            ):
                figure.add_bar(
                    x=df["month"],
                    y=df[column] / denominator * 100,
                    name=name,
                    marker_color=color,
                )
            figure.update_layout(
                title="Asset Allocation (%)",
                barmode="stack",
                yaxis=dict(title="Ratio (%)", range=[0, 100]),
            )
            return figure

        return self._cached("allocation", months, forecast, build)

    def get_ratios_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        def build(df: pd.DataFrame) -> go.Figure:
            figure = go.Figure()
            figure.add_scatter(
                x=df["month"],
                y=df["savings_rate"] * 100,
                name="Savings Rate (%)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["navy"], width=3),
            )
            figure.add_scatter(
                x=df["month"],
                y=df["risk_asset_ratio"] * 100,
                name="Invested Asset Ratio (%)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["gold"], width=3),
            )
            figure.update_layout(title="Financial Ratios (%)", yaxis_title="Ratio (%)")
            return figure

        return self._cached("ratios", months, forecast, build)

    def get_returns_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        def build(df: pd.DataFrame) -> go.Figure:
            figure = go.Figure()
            for column, name, color, dash in (
                ("monthly_return", "Portfolio Return (%)", CHART_COLORS["navy"], None),
                ("benchmark_return", "Benchmark Return (%)", CHART_COLORS["slate"], "dot"),
                ("monthly_alpha", "Alpha (%)", CHART_COLORS["gold"], None),
            ):
                figure.add_scatter(
                    x=df["month"],
                    y=df[column] * 100,
                    name=name,
                    mode="lines+markers",
                    line=dict(color=color, width=3, dash=dash),
                )
            figure.update_layout(
                title="Investment Performance (%)", yaxis_title="Return (%)"
            )
            return figure

        return self._cached("returns", months, forecast, build)

    def get_fi_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        def build(df: pd.DataFrame) -> go.Figure:
            figure = go.Figure()
            for column, name, color, dash in (
                ("fi_ratio_12m", "FI Ratio (12m)", CHART_COLORS["navy"], None),
                ("fi_ratio_48m", "FI Ratio (48m)", CHART_COLORS["sage"], None),
                ("fi_ratio_next_12m", "FI Ratio (Projected)", CHART_COLORS["gold"], "dot"),
            ):
                figure.add_scatter(
                    x=df["month"],
                    y=df[column],
                    name=name,
                    mode="lines+markers",
                    line=dict(color=color, width=3, dash=dash),
                )
            figure.update_layout(
                title="Financial Independence Ratio", yaxis_title="Ratio (x Expenses)"
            )
            return figure

        return self._cached("fi", months, forecast, build)
