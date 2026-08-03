from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable, List

from src.constants import PORTFOLIO_EXPECTED_ANNUAL_RETURN
from src.domain.entities.models import Market, Month
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

            if bs.return_base_assets > 0:
                raw_return = bs.investment_gain_loss / bs.return_base_assets
            else:
                raw_return = math.nan
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
            alpha = (
                monthly_return - benchmark_return
                if math.isfinite(monthly_return) and math.isfinite(benchmark_return)
                else math.nan
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

            savings_rate = savings_12m / income_12m if income_12m else 0.0
            risk_ratio = (
                (bs.risk_assets + bs.pension_assets) / bs.total_financial_assets
                if bs.total_financial_assets
                else 0.0
            )
            fi_12 = gain_12m / expense_12m if expense_12m else 0.0
            fi_48 = gain_48m / expense_48m if expense_48m else 0.0
            fi_next = (
                (bs.risk_assets + bs.pension_assets)
                * PORTFOLIO_EXPECTED_ANNUAL_RETURN
                / expense_12m
                if expense_12m
                else 0.0
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
