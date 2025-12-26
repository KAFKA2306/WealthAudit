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
        """Load a CSV file from the calculated data directory."""
        path = os.path.join(self.data_dir, "data", "calculated", filename)
        return pd.read_csv(path)

    def _filter_months(self, df: pd.DataFrame, months: Optional[int]) -> pd.DataFrame:
        """Filter dataframe to last N months if specified."""
        if months is not None and len(df) > months:
            return df.tail(months)
        return df

    def get_net_worth_chart(self, months: Optional[int] = None) -> str:
        """Generate stacked bar chart for net worth trend."""
        df = self._load_csv("balance_sheet.csv")
        df = self._filter_months(df, months)

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
            title="Net Worth Trend (万円)",
            xaxis_title="Month",
            yaxis_title="Amount (万円)",
            barmode="stack",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=60, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_cashflow_chart(self, months: Optional[int] = None) -> str:
        """Generate bar chart for monthly cash flow."""
        df = self._load_csv("cashflow.csv")
        df = self._filter_months(df, months)

        # Calculate 6-month moving averages
        income_6ma = df["after_tax_income"].rolling(window=6, min_periods=1).mean()
        net_savings_6ma = df["net_savings"].rolling(window=6, min_periods=1).mean()

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
                y=income_6ma,
                name="Income (6MA)",
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
            go.Scatter(
                x=df["month"],
                y=df["net_savings"],
                name="Net Savings",
                mode="lines+markers",
                line=dict(color="rgba(59, 130, 246, 1)", width=2),
                marker=dict(size=6),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=net_savings_6ma,
                name="Net Savings (6MA)",
                mode="lines",
                line=dict(color="rgba(245, 158, 11, 1)", width=3, dash="dash"),
            )
        )

        fig.update_layout(
            title="Monthly Cash Flow (万円)",
            xaxis_title="Month",
            yaxis_title="Amount (万円)",
            barmode="relative",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=60, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_allocation_chart(self, months: Optional[int] = None) -> str:
        """Generate 100% stacked bar chart for asset allocation trend."""
        df = self._load_csv("balance_sheet.csv")
        df = self._filter_months(df, months)

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
            title="Asset Allocation (%)",
            xaxis_title="Month",
            yaxis_title="Ratio (%)",
            barmode="stack",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=60, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            yaxis=dict(range=[0, 100]),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_ratios_chart(self, months: Optional[int] = None) -> str:
        """Generate line chart for savings rate and risk asset ratio."""
        df = self._load_csv("metrics.csv")
        df = self._filter_months(df, months)

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
            title="Financial Ratios (%)",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=60, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            yaxis=dict(title="Ratio (%)"),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_returns_chart(self, months: Optional[int] = None) -> str:
        """Generate line chart for investment returns."""
        df = self._load_csv("metrics.csv")
        df = self._filter_months(df, months)

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
            title="Investment Performance (%)",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=60, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            yaxis=dict(title="Return (%)"),
        )

        return cast(str, fig.to_html(full_html=False, include_plotlyjs="cdn"))

    def get_fi_chart(self, months: Optional[int] = None) -> str:
        """Generate line chart for Financial Independence ratios."""
        df = self._load_csv("metrics.csv")
        df = self._filter_months(df, months)

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
            title="Financial Independence Ratio (Years Covered)",
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=60, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
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
