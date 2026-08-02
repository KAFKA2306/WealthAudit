import os

import pandas as pd
from injector import Injector

from src.domain.repositories.interfaces import (
    IAssetRepository,
    IMarketRepository,
    IMasterRepository,
    ITransactionRepository,
)
from src.infrastructure.di.container import AppModule
from src.use_cases.calculators.balance_sheet import BalanceSheetCalculator
from src.use_cases.calculators.cash_flow import CashFlowCalculator
from src.use_cases.calculators.metrics import MetricsCalculator


def main() -> None:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    injector = Injector([AppModule(root_dir)])

    transaction_repo = injector.get(ITransactionRepository)  # type: ignore
    asset_repo = injector.get(IAssetRepository)  # type: ignore
    market_repo = injector.get(IMarketRepository)  # type: ignore
    master_repo = injector.get(IMasterRepository)  # type: ignore

    cf_calculator = injector.get(CashFlowCalculator)
    bs_calculator = injector.get(BalanceSheetCalculator)
    metrics_calculator = injector.get(MetricsCalculator)

    incomes = transaction_repo.get_incomes()
    expenses = transaction_repo.get_expenses()
    assets = asset_repo.get_assets()
    markets = market_repo.get_market_data()
    accounts = master_repo.get_accounts()
    asset_classes = master_repo.get_asset_classes()

    cashflows = cf_calculator.calculate(incomes, expenses, accounts)
    balance_sheets = bs_calculator.calculate(
        assets, markets, accounts, cashflows, asset_classes
    )
    metrics = metrics_calculator.calculate(cashflows, balance_sheets, markets)

    output_dir = os.path.join(root_dir, "data", "calculated")
    os.makedirs(output_dir, exist_ok=True)

    pd.DataFrame(
        [
            {
                "month": item.month,
                "after_tax_income": item.after_tax_income / 10000,
                "expenditure": item.expenditure / 10000,
                "net_savings": item.net_savings / 10000,
                "asset_contribution": item.asset_contribution / 10000,
                "net_worth_contribution": item.net_worth_contribution / 10000,
            }
            for item in cashflows
        ]
    ).to_csv(os.path.join(output_dir, "cashflow.csv"), index=False)

    pd.DataFrame(
        [
            {
                "month": item.month,
                "liquid_assets": item.liquid_assets / 10000,
                "risk_assets": item.risk_assets / 10000,
                "pension_assets": item.pension_assets / 10000,
                "total_financial_assets": item.total_financial_assets / 10000,
                "investment_gain_loss": item.investment_gain_loss / 10000,
                "return_base_assets": item.return_base_assets / 10000,
            }
            for item in balance_sheets
        ]
    ).to_csv(os.path.join(output_dir, "balance_sheet.csv"), index=False)

    pd.DataFrame(
        [
            {
                "month": item.month,
                "savings_rate": item.savings_rate,
                "risk_asset_ratio": item.risk_asset_ratio,
                "raw_monthly_return": item.raw_monthly_return,
                "monthly_return": item.monthly_return,
                "raw_benchmark_return": item.raw_benchmark_return,
                "benchmark_return": item.benchmark_return,
                "monthly_alpha": item.monthly_alpha,
                "fi_ratio_12m": item.fi_ratio_12m,
                "fi_ratio_48m": item.fi_ratio_48m,
                "fi_ratio_next_12m": item.fi_ratio_next_12m,
            }
            for item in metrics
        ]
    ).to_csv(os.path.join(output_dir, "metrics.csv"), index=False)

    print(f"Successfully exported to {output_dir}")


if __name__ == "__main__":
    main()
