from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable, List

from src.constants import PORTFOLIO_EXPECTED_ANNUAL_RETURN
from src.domain.entities.models import Market, Month
from src.use_cases.calculators.formula_manifest import evaluate_formula
from src.use_cases.dtos.output import BalanceSheet, CashFlowStatement, FinancialMetrics
from src.use_cases.valuation import previous_month


def _calendar_months_ending(month: str, count: int) -> list[str]:
    end = datetime.strptime(month, "%Y-%m")
    result: list[str] = []
    year = end.year
    month_number = end.month
    for _ in range(count):
        result.append(f"{year:04d}-{month_number:02d}")
        month_number -= 1
        if month_number == 0:
            year -= 1
            month_number = 12
    return result


def _geometric_mean(values: Iterable[float]) -> float:
    usable = [value for value in values if math.isfinite(value) and value > -1]
    if not usable:
        return math.nan
    product = 1.0
    for value in usable:
        product *= 1.0 + value
    return float(product ** (1.0 / len(usable)) - 1.0)


class MetricsCalculator:
    def calculate(
        self,
        cf_statements: List[CashFlowStatement],
        bs_statements: List[BalanceSheet],
        markets: List[Market],
    ) -> List[FinancialMetrics]:
        cf_map = {str(item.month): item for item in cf_statements}
        bs_map = {str(item.month): item for item in bs_statements}
        market_map = {str(item.month): item for item in markets}
        raw_returns: dict[str, float] = {}
        raw_benchmarks: dict[str, float] = {}
        metrics: list[FinancialMetrics] = []

        for month in sorted(set(cf_map) & set(bs_map)):
            bs = bs_map[month]
            previous = previous_month(month)

            raw_return = evaluate_formula(
                "raw_monthly_return",
                {
                    "investment_gain_loss": bs.investment_gain_loss,
                    "return_base_assets": bs.return_base_assets,
                },
            )
            raw_returns[month] = raw_return

            current_market = market_map.get(month)
            previous_market = market_map.get(previous)
            raw_benchmark = math.nan
            if current_market is not None and previous_market is not None:
                current_value = current_market.sp500 * current_market.usd_jpy
                previous_value = previous_market.sp500 * previous_market.usd_jpy
                if previous_value > 0:
                    raw_benchmark = current_value / previous_value - 1.0
            raw_benchmarks[month] = raw_benchmark

            trailing_months = _calendar_months_ending(month, 12)
            monthly_return = _geometric_mean(
                raw_returns.get(item, math.nan) for item in trailing_months
            )
            benchmark_return = _geometric_mean(
                raw_benchmarks.get(item, math.nan) for item in trailing_months
            )
            alpha = evaluate_formula(
                "monthly_alpha",
                {"monthly_return": monthly_return, "benchmark_return": benchmark_return},
            )

            income_12m = sum(
                cf_map[item].after_tax_income
                for item in trailing_months
                if item in cf_map
            )
            savings_12m = sum(
                cf_map[item].net_savings for item in trailing_months if item in cf_map
            )
            expense_12m = sum(
                cf_map[item].expenditure for item in trailing_months if item in cf_map
            )
            gain_12m = sum(
                bs_map[item].investment_gain_loss
                for item in trailing_months
                if item in bs_map
            )
            trailing_48 = _calendar_months_ending(month, 48)
            expense_48m = sum(
                cf_map[item].expenditure for item in trailing_48 if item in cf_map
            )
            gain_48m = sum(
                bs_map[item].investment_gain_loss
                for item in trailing_48
                if item in bs_map
            )

            risk_and_pension_assets = bs.risk_assets + bs.pension_assets
            savings_rate = evaluate_formula(
                "savings_rate_12m",
                {
                    "net_savings_12m": savings_12m,
                    "after_tax_income_12m": income_12m,
                },
            )
            risk_ratio = evaluate_formula(
                "risk_asset_ratio",
                {
                    "risk_and_pension_assets": risk_and_pension_assets,
                    "total_financial_assets": bs.total_financial_assets,
                },
            )
            fi_12 = evaluate_formula(
                "fi_ratio_12m",
                {
                    "investment_gain_loss_12m": gain_12m,
                    "expenditure_12m": expense_12m,
                },
            )
            fi_48 = evaluate_formula(
                "fi_ratio_48m",
                {
                    "investment_gain_loss_48m": gain_48m,
                    "expenditure_48m": expense_48m,
                },
            )
            fi_next = evaluate_formula(
                "fi_ratio_next_12m",
                {
                    "risk_and_pension_assets": risk_and_pension_assets,
                    "expected_annual_return": PORTFOLIO_EXPECTED_ANNUAL_RETURN,
                    "expenditure_12m": expense_12m,
                },
            )

            metrics.append(
                FinancialMetrics(
                    month=Month(month),
                    savings_rate=savings_rate,
                    risk_asset_ratio=risk_ratio,
                    raw_monthly_return=raw_return,
                    monthly_return=monthly_return,
                    raw_benchmark_return=raw_benchmark,
                    benchmark_return=benchmark_return,
                    monthly_alpha=alpha,
                    fi_ratio_12m=fi_12,
                    fi_ratio_48m=fi_48,
                    fi_ratio_next_12m=fi_next,
                )
            )

        return metrics
