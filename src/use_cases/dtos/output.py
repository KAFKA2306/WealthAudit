from __future__ import annotations

import math
from dataclasses import dataclass

from src.domain.entities.models import Month


@dataclass(init=False)
class CashFlowStatement:
    month: Month
    after_tax_income: int
    expenditure: int
    net_savings: int
    asset_contribution: int = 0
    net_worth_contribution: int

    def __init__(
        self,
        month: Month,
        after_tax_income: int,
        expenditure: int,
        net_savings: int,
        asset_contribution: int = 0,
        net_worth_contribution: int | None = None,
    ) -> None:
        self.month = month
        self.after_tax_income = after_tax_income
        self.expenditure = expenditure
        self.net_savings = net_savings
        self.asset_contribution = asset_contribution
        self.net_worth_contribution = (
            net_savings + asset_contribution
            if net_worth_contribution is None
            else net_worth_contribution
        )


@dataclass
class BalanceSheet:
    month: Month
    liquid_assets: int
    risk_assets: int
    pension_assets: int
    total_financial_assets: int
    investment_gain_loss: int
    return_base_assets: int = 0


@dataclass
class FinancialMetrics:
    month: Month
    savings_rate: float
    risk_asset_ratio: float
    monthly_return: float
    monthly_alpha: float
    benchmark_return: float
    fi_ratio_12m: float
    fi_ratio_48m: float
    fi_ratio_next_12m: float
    raw_monthly_return: float = math.nan
    raw_benchmark_return: float = math.nan
