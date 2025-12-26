"""Graph generation service for financial data visualization."""

import os
from dataclasses import dataclass
from typing import Optional, cast

import pandas as pd
import plotly.graph_objects as go


@dataclass
class GraphService:
    """Service for generating Plotly HTML chart fragments."""

    data_dir: str

    def _load_csv(self, filename: str) -> pd.DataFrame:
        path = os.path.join(self.data_dir, "data", "calculated", filename)
        return pd.read_csv(path)

    def _filter_data(
        self, df: pd.DataFrame, months: Optional[int], forecast: Optional[int]
    ) -> pd.DataFrame:
        current = "2025-12"
        if forecast:
            start = (pd.to_datetime(current) - pd.DateOffset(months=12)).strftime("%Y-%m")
            end = (pd.to_datetime(current) + pd.DateOffset(months=forecast)).strftime("%Y-%m")
            return df[(df["month"] >= start) & (df["month"] <= end)]
        if months:
            return df[df["month"] <= current].tail(months)
        return df[df["month"] <= current]

    def get_net_worth_chart(self, months: Optional[int] = None, forecast: Optional[int] = None) -> str:
        """Generate stacked bar chart for net worth trend."""
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["liquid_assets"],
                name="Liquid Assets",
                marker_color="rgba(59, 130, 246, 0.8)",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["risk_assets"],
                name="Risk Assets",
                marker_color="rgba(16, 185, 129, 0.8)",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["pension_assets"],
                name="Pension Assets",
                marker_color="rgba(139, 92, 246, 0.8)",
            )
        )

        fig.update_layout(
            title=dict(text="Net Worth Trend (万円)", y=0.98, x=0.5, xanchor="center"),
            xaxis_title="Month",
            yaxis_title="Amount (万円)",
            barmode="stack",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1
            ),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_cashflow_chart(self, months: Optional[int] = None, forecast: Optional[int] = None) -> str:
        """Generate bar chart for monthly cash flow."""
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        income_12ma = df["after_tax_income"].rolling(window=12, min_periods=1).mean()

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["after_tax_income"],
                name="Income",
                marker_color="rgba(16, 185, 129, 0.8)",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=income_12ma,
                name="Income (12MA)",
                mode="lines",
                line=dict(color="rgba(16, 185, 129, 1)", width=3, dash="dash"),
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=-df["expenditure"],
                name="Expenses",
                marker_color="rgba(239, 68, 68, 0.8)",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["investment_gain_loss"],
                name="Investment G/L",
                marker_color="rgba(139, 92, 246, 0.8)",
            )
        )

        total_flow = df["net_savings"] + df["investment_gain_loss"]
        total_flow_12ma = total_flow.rolling(window=12, min_periods=1).mean()

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=total_flow,
                name="Total Flow",
                mode="lines+markers",
                line=dict(color="rgba(59, 130, 246, 1)", width=2),
                marker=dict(size=6),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=total_flow_12ma,
                name="Total Flow (12MA)",
                mode="lines",
                line=dict(color="rgba(245, 158, 11, 1)", width=3, dash="dash"),
            )
        )


        fig.update_layout(
            title=dict(text="Monthly Cash Flow (万円)", y=0.98, x=0.5, xanchor="center"),
            xaxis_title="Month",
            yaxis_title="Amount (万円)",
            barmode="relative",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1
            ),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_allocation_chart(self, months: Optional[int] = None, forecast: Optional[int] = None) -> str:
        """Generate 100% stacked bar chart for asset allocation trend."""
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        # Calculate percentages
        total = df["liquid_assets"] + df["risk_assets"] + df["pension_assets"]
        liquid_pct = df["liquid_assets"] / total * 100
        risk_pct = df["risk_assets"] / total * 100
        pension_pct = df["pension_assets"] / total * 100

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=liquid_pct,
                name="Liquid Assets",
                marker_color="rgba(59, 130, 246, 0.8)",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=risk_pct,
                name="Risk Assets",
                marker_color="rgba(16, 185, 129, 0.8)",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=pension_pct,
                name="Pension Assets",
                marker_color="rgba(139, 92, 246, 0.8)",
            )
        )

        fig.update_layout(
            title=dict(text="Asset Allocation (%)", y=0.98, x=0.5, xanchor="center"),
            xaxis_title="Month",
            yaxis_title="Ratio (%)",
            barmode="stack",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1
            ),
            yaxis=dict(range=[0, 100]),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_ratios_chart(self, months: Optional[int] = None, forecast: Optional[int] = None) -> str:
        """Generate line chart for savings rate and risk asset ratio."""
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["savings_rate"] * 100,
                name="Savings Rate (%)",
                mode="lines+markers",
                line=dict(color="rgba(59, 130, 246, 1)", width=2),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["risk_asset_ratio"] * 100,
                name="Risk Asset Ratio (%)",
                mode="lines+markers",
                line=dict(color="rgba(16, 185, 129, 1)", width=2),
            )
        )

        fig.update_layout(
            title=dict(text="Financial Ratios (%)", y=0.98, x=0.5, xanchor="center"),
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1
            ),
            yaxis=dict(title="Ratio (%)"),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_returns_chart(self, months: Optional[int] = None, forecast: Optional[int] = None) -> str:
        """Generate line chart for investment returns."""
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["monthly_return"] * 100,
                name="Monthly Return (%)",
                mode="lines+markers",
                line=dict(color="rgba(59, 130, 246, 1)", width=2),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["benchmark_return"] * 100,
                name="Benchmark Return (%)",
                mode="lines+markers",
                line=dict(color="rgba(148, 163, 184, 1)", width=2, dash="dot"),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["monthly_alpha"] * 100,
                name="Alpha (%)",
                mode="lines+markers",
                line=dict(color="rgba(139, 92, 246, 1)", width=2),
            )
        )

        fig.update_layout(
            title=dict(text="Investment Performance (%)", y=0.98, x=0.5, xanchor="center"),
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1
            ),
            yaxis=dict(title="Return (%)"),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_fi_chart(self, months: Optional[int] = None, forecast: Optional[int] = None) -> str:
        """Generate line chart for Financial Independence ratios."""
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["fi_ratio_12m"],
                name="FI Ratio (12m)",
                mode="lines+markers",
                line=dict(color="rgba(59, 130, 246, 1)", width=2),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["fi_ratio_48m"],
                name="FI Ratio (48m)",
                mode="lines+markers",
                line=dict(color="rgba(16, 185, 129, 1)", width=2),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["fi_ratio_next_12m"],
                name="FI Ratio (Proj)",
                mode="lines+markers",
                line=dict(color="rgba(245, 158, 11, 1)", width=2, dash="dot"),
            )
        )

        fig.update_layout(
            title=dict(text="Financial Independence Ratio (Years Covered)", y=0.98, x=0.5, xanchor="center"),
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1
            ),
            yaxis=dict(title="Ratio (x Expenses)"),
            shapes=[
                dict(
                    type="line",
                    yref="y",
                    y0=1.0,
                    y1=1.0,
                    xref="paper",
                    x0=0,
                    x1=1,
                    line=dict(
                        color="rgba(239, 68, 68, 0.5)",
                        width=2,
                        dash="dashdot",
                    ),
                    name="FIRE Target (100%)",
                )
            ],
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))
