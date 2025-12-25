import os
import pandas as pd
from injector import Injector
from src.infrastructure.di.container import AppModule
from src.domain.repositories.interfaces import (
    ITransactionRepository,
    IAssetRepository,
    IMarketRepository,
    IMasterRepository,
)
from src.use_cases.calculators.cash_flow import CashFlowCalculator
from src.use_cases.calculators.balance_sheet import BalanceSheetCalculator
from src.use_cases.calculators.metrics import MetricsCalculator


def main() -> None:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    injector = Injector([AppModule(root_dir)])

    # Repositories
    transaction_repo = injector.get(ITransactionRepository)  # type: ignore
    asset_repo = injector.get(IAssetRepository)  # type: ignore
    market_repo = injector.get(IMarketRepository)  # type: ignore
    master_repo = injector.get(IMasterRepository)  # type: ignore

    # Calculators
    cf_calculator = injector.get(CashFlowCalculator)
    bs_calculator = injector.get(BalanceSheetCalculator)
    metrics_calculator = injector.get(MetricsCalculator)

    print("Loading data...")
    incomes = transaction_repo.get_incomes()
    expenses = transaction_repo.get_expenses()
    assets = asset_repo.get_assets()
    markets = market_repo.get_market_data()
    accounts = master_repo.get_accounts()

    print("Calculating Cash Flow...")
    cf_statements = cf_calculator.calculate(incomes, expenses)

    print("Calculating Balance Sheet...")
    bs_statements = bs_calculator.calculate(assets, markets, accounts, cf_statements)

    print("Calculating Metrics...")
    metrics = metrics_calculator.calculate(cf_statements, bs_statements, markets)

    # Export
    output_dir = os.path.join(root_dir, "data", "calculated")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Cash Flow
    cf_data = []
    for cf in cf_statements:
        cf_data.append(
            {
                "month": cf.month,
                "after_tax_income": cf.after_tax_income / 10000,  # Convert to Man-Yen
                "expenditure": cf.expenditure / 10000,
                "net_savings": cf.net_savings / 10000,
            }
        )
    pd.DataFrame(cf_data).to_csv(
        os.path.join(output_dir, "cashflow.csv"), index=False, float_format="%.4g"
    )

    # 2. Balance Sheet
    bs_data = []
    for bs in bs_statements:
        bs_data.append(
            {
                "month": bs.month,
                "liquid_assets": bs.liquid_assets / 10000,
                "risk_assets": bs.risk_assets / 10000,
                "pension_assets": bs.pension_assets / 10000,
                "total_financial_assets": bs.total_financial_assets / 10000,
                "investment_gain_loss": bs.investment_gain_loss / 10000,
            }
        )
    pd.DataFrame(bs_data).to_csv(
        os.path.join(output_dir, "balance_sheet.csv"), index=False, float_format="%.4g"
    )

    # 3. Metrics
    metrics_data = []
    for m in metrics:
        metrics_data.append(
            {
                "month": m.month,
                "savings_rate": m.savings_rate,
                "risk_asset_ratio": m.risk_asset_ratio,
                "monthly_return": m.monthly_return,
                "monthly_alpha": m.monthly_alpha,
                "benchmark_return": m.benchmark_return,
                "fi_ratio_12m": m.fi_ratio_12m,
                "fi_ratio_48m": m.fi_ratio_48m,
                "fi_ratio_next_12m": m.fi_ratio_next_12m,
            }
        )
    pd.DataFrame(metrics_data).to_csv(
        os.path.join(output_dir, "metrics.csv"), index=False, float_format="%.4g"
    )

    print(f"Successfully exported to {output_dir}")


if __name__ == "__main__":
    main()
