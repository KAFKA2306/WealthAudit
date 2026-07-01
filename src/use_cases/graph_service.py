import os
from dataclasses import dataclass
from typing import Optional, cast

from datetime import datetime
import pandas as pd
import plotly.graph_objects as go

CHART_COLORS = {
    "navy": "#17233f",
    "ink": "#13233f",
    "muted": "#788291",
    "gold": "#c99a3a",
    "champagne": "#f1dfb5",
    "sage": "#738b73",
    "rose": "#b87460",
    "slate": "#7d8998",
}


@dataclass
class GraphService:

    data_dir: str

    def _to_html(self, fig: go.Figure) -> str:
        fig.update_layout(
            font=dict(family="Manrope, Arial, sans-serif", color=CHART_COLORS["ink"]),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,255,255,0)",
            title=dict(
                font=dict(
                    family="Playfair Display, Georgia, serif",
                    size=24,
                    color=CHART_COLORS["navy"],
                )
            ),
            hoverlabel=dict(
                bgcolor="#ffffff",
                bordercolor="rgba(201, 154, 58, 0.28)",
                font=dict(color=CHART_COLORS["ink"]),
            ),
            xaxis=dict(
                gridcolor="rgba(19, 35, 63, 0.06)",
                linecolor="rgba(19, 35, 63, 0.12)",
                tickfont=dict(color=CHART_COLORS["muted"]),
                title_font=dict(color=CHART_COLORS["muted"]),
                zerolinecolor="rgba(19, 35, 63, 0.08)",
            ),
            yaxis=dict(
                gridcolor="rgba(19, 35, 63, 0.06)",
                linecolor="rgba(19, 35, 63, 0.12)",
                tickfont=dict(color=CHART_COLORS["muted"]),
                title_font=dict(color=CHART_COLORS["muted"]),
                zerolinecolor="rgba(19, 35, 63, 0.08)",
            ),
            legend=dict(
                font=dict(color=CHART_COLORS["muted"], size=12),
                bgcolor="rgba(255,255,255,0)",
            ),
        )
        return cast(
            str,
            fig.to_html(
                full_html=False,
                include_plotlyjs=False,
                default_width="100%",
                config={
                    "displayModeBar": False,
                    "responsive": True,
                },
            ),
        )

    def _load_csv(self, filename: str) -> pd.DataFrame:
        path = os.path.join(self.data_dir, "data", "calculated", filename)
        return pd.read_csv(path)

    def _filter_data(
        self, df: pd.DataFrame, months: Optional[int], forecast: Optional[int]
    ) -> pd.DataFrame:
        current = datetime.now().strftime("%Y-%m")
        if forecast:
            start = (pd.to_datetime(current) - pd.DateOffset(months=12)).strftime(
                "%Y-%m"
            )
            end = (pd.to_datetime(current) + pd.DateOffset(months=forecast)).strftime(
                "%Y-%m"
            )
            return df[(df["month"] >= start) & (df["month"] <= end)]
        if months:
            return df[df["month"] <= current].tail(months)
        return df[df["month"] <= current]

    def get_net_worth_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        # 合計値の計算
        total = df["liquid_assets"] + df["risk_assets"] + df["pension_assets"]

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["liquid_assets"],
                name="Liquid Assets",
                marker_color="rgba(23, 35, 63, 0.88)",
                hovertemplate="Liquid Assets: %{y:,.0f}万円<extra></extra>",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["risk_assets"],
                name="Risk Assets",
                marker_color="rgba(201, 154, 58, 0.82)",
                hovertemplate="Risk Assets: %{y:,.0f}万円<extra></extra>",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["pension_assets"],
                name="Pension Assets",
                marker_color="rgba(115, 139, 115, 0.78)",
                hovertemplate="Pension Assets: %{y:,.0f}万円<extra></extra>",
            )
        )

        # 合計を表示するための隠しトレース
        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=total,
                name="TOTAL",
                mode="lines",
                line=dict(width=0),
                hovertemplate="<b>TOTAL: %{y:,.0f}万円</b><extra></extra>",
                showlegend=False,
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

        return self._to_html(fig)

    def get_cashflow_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        income_12ma = df["after_tax_income"].rolling(window=12, min_periods=1).mean()

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["after_tax_income"],
                name="Income",
                marker_color="rgba(115, 139, 115, 0.8)",
                hovertemplate="Income: %{y:,.1f}万円<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=income_12ma,
                name="Income (12MA)",
                mode="lines",
                line=dict(color=CHART_COLORS["sage"], width=3, dash="dash"),
                hovertemplate="Income (12MA): %{y:,.1f}万円<extra></extra>",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=-df["expenditure"],
                name="Expenses",
                marker_color="rgba(184, 116, 96, 0.74)",
                hovertemplate="Expenses: %{y:,.1f}万円<extra></extra>",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=df["investment_gain_loss"],
                name="Investment G/L",
                marker_color="rgba(201, 154, 58, 0.76)",
                hovertemplate="Inv G/L: %{y:,.1f}万円<extra></extra>",
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
                line=dict(color=CHART_COLORS["navy"], width=3),
                marker=dict(size=7, color=CHART_COLORS["navy"]),
                hovertemplate="<b>Total Flow: %{y:,.1f}万円</b><extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=total_flow_12ma,
                name="Total Flow (12MA)",
                mode="lines",
                line=dict(color=CHART_COLORS["gold"], width=3, dash="dash"),
                hovertemplate="Flow (12MA): %{y:,.1f}万円<extra></extra>",
            )
        )

        fig.update_layout(
            title=dict(
                text="Monthly Cash Flow (万円)", y=0.98, x=0.5, xanchor="center"
            ),
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

        return self._to_html(fig)

    def get_allocation_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

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
                marker_color="rgba(23, 35, 63, 0.88)",
                hovertemplate="Liquid: %{y:.1f}%<extra></extra>",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=risk_pct,
                name="Risk Assets",
                marker_color="rgba(201, 154, 58, 0.82)",
                hovertemplate="Risk: %{y:.1f}%<extra></extra>",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["month"],
                y=pension_pct,
                name="Pension Assets",
                marker_color="rgba(115, 139, 115, 0.78)",
                hovertemplate="Pension: %{y:.1f}%<extra></extra>",
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

        return self._to_html(fig)

    def get_ratios_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["savings_rate"] * 100,
                name="Savings Rate (%)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["navy"], width=3),
                marker=dict(size=7, color=CHART_COLORS["navy"]),
                hovertemplate="Savings Rate: %{y:.1f}%<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["risk_asset_ratio"] * 100,
                name="Risk Asset Ratio (%)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["gold"], width=3),
                marker=dict(size=7, color=CHART_COLORS["gold"]),
                hovertemplate="Risk Asset Ratio: %{y:.1f}%<extra></extra>",
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

        return self._to_html(fig)

    def get_returns_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["monthly_return"] * 100,
                name="Monthly Return (%)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["navy"], width=3),
                marker=dict(size=7, color=CHART_COLORS["navy"]),
                hovertemplate="My Return: %{y:.2f}%<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["benchmark_return"] * 100,
                name="Benchmark Return (%)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["slate"], width=2, dash="dot"),
                marker=dict(size=6, color=CHART_COLORS["slate"]),
                hovertemplate="Benchmark: %{y:.2f}%<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["monthly_alpha"] * 100,
                name="Alpha (%)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["gold"], width=3),
                marker=dict(size=7, color=CHART_COLORS["gold"]),
                hovertemplate="Alpha: %{y:.2f}%<extra></extra>",
            )
        )

        fig.update_layout(
            title=dict(
                text="Investment Performance (%)", y=0.98, x=0.5, xanchor="center"
            ),
            hovermode="x unified",
            template="plotly_white",
            margin=dict(l=40, r=40, t=100, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1
            ),
            yaxis=dict(title="Return (%)"),
        )

        return self._to_html(fig)

    def get_fi_chart(
        self, months: Optional[int] = None, forecast: Optional[int] = None
    ) -> str:
        df = self._load_csv("forecast.csv")
        df = self._filter_data(df, months, forecast)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["fi_ratio_12m"],
                name="FI Ratio (12m)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["navy"], width=3),
                marker=dict(size=7, color=CHART_COLORS["navy"]),
                hovertemplate="FI Ratio (12m): %{y:.2f}x<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["fi_ratio_48m"],
                name="FI Ratio (48m)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["sage"], width=3),
                marker=dict(size=7, color=CHART_COLORS["sage"]),
                hovertemplate="FI Ratio (48m): %{y:.2f}x<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["fi_ratio_next_12m"],
                name="FI Ratio (Proj)",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["gold"], width=3, dash="dot"),
                marker=dict(size=7, color=CHART_COLORS["gold"]),
                hovertemplate="FI Ratio (Proj): %{y:.2f}x<extra></extra>",
            )
        )

        fig.update_layout(
            title=dict(
                text="Financial Independence Ratio (Years Covered)",
                y=0.98,
                x=0.5,
                xanchor="center",
            ),
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
                        color="rgba(184, 116, 96, 0.58)",
                        width=2,
                        dash="dashdot",
                    ),
                    name="FIRE Target (100%)",
                )
            ],
        )

        return self._to_html(fig)
