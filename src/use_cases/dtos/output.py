from dataclasses import dataclass
from src.domain.entities.models import Month


@dataclass
class CashFlowStatement:
    month: Month
    after_tax_income: int
    expenditure: int
    net_savings: int


@dataclass
class BalanceSheet:
    month: Month
    liquid_assets: int
    risk_assets: int
    pension_assets: int
    total_financial_assets: int
    investment_gain_loss: int


@dataclass
class FinancialMetrics:
    month: Month
    savings_rate: float
    risk_asset_ratio: float
    monthly_return: float
    monthly_alpha: float
