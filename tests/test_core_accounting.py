from src.constants import AccountId, AccountType, AssetClassId, Currency, PaymentMethodId
from src.domain.entities.models import Account, Asset, Expense, Income, Month
from src.use_cases.calculators.balance_sheet import BalanceSheetCalculator
from src.use_cases.calculators.cash_flow import CashFlowCalculator
from src.use_cases.calculators.metrics import MetricsCalculator
from src.use_cases.dtos.output import BalanceSheet, CashFlowStatement


def _account(
    account_id: AccountId,
    account_type: AccountType,
    risk: int = 0,
) -> Account:
    return Account(
        id=account_id,
        name=account_id.value,
        type=account_type,
        currency=Currency.JPY,
        risk=risk,
    )


def test_pension_only_asset_increase_is_not_investment_gain_loss() -> None:
    accounts = [_account(AccountId.DC, AccountType.PENSION, risk=1)]
    cashflows = CashFlowCalculator().calculate(
        incomes=[Income(Month("2026-02"), AccountId.DC, 10_000)],
        expenses=[],
        accounts=accounts,
    )

    balance_sheets = BalanceSheetCalculator().calculate(
        assets=[
            Asset(Month("2026-01"), AccountId.DC, AssetClassId.PENSION, 100_000),
            Asset(Month("2026-02"), AccountId.DC, AssetClassId.PENSION, 110_000),
        ],
        markets=[],
        accounts=accounts,
        cashflows=cashflows,
    )

    assert cashflows[0].after_tax_income == 0
    assert cashflows[0].asset_contribution == 10_000
    assert balance_sheets[1].investment_gain_loss == 0


def test_cash_income_and_expense_produce_cash_savings() -> None:
    accounts = [_account(AccountId.YUCHO, AccountType.BANK)]

    cashflows = CashFlowCalculator().calculate(
        incomes=[Income(Month("2026-01"), AccountId.YUCHO, 300_000)],
        expenses=[Expense(Month("2026-01"), PaymentMethodId.CASH, 120_000)],
        accounts=accounts,
    )

    assert cashflows[0].after_tax_income == 300_000
    assert cashflows[0].expenditure == 120_000
    assert cashflows[0].net_savings == 180_000
    assert cashflows[0].asset_contribution == 0
    assert cashflows[0].net_worth_contribution == 180_000


def test_mixed_cash_savings_and_asset_contribution_are_net_worth_contribution() -> None:
    accounts = [
        _account(AccountId.YUCHO, AccountType.BANK),
        _account(AccountId.DC, AccountType.PENSION, risk=1),
    ]

    cashflows = CashFlowCalculator().calculate(
        incomes=[
            Income(Month("2026-02"), AccountId.YUCHO, 300_000),
            Income(Month("2026-02"), AccountId.DC, 50_000),
        ],
        expenses=[Expense(Month("2026-02"), PaymentMethodId.CASH, 200_000)],
        accounts=accounts,
    )

    balance_sheets = BalanceSheetCalculator().calculate(
        assets=[
            Asset(Month("2026-01"), AccountId.YUCHO, AssetClassId.CASH, 1_000_000),
            Asset(Month("2026-01"), AccountId.DC, AssetClassId.PENSION, 500_000),
            Asset(Month("2026-02"), AccountId.YUCHO, AssetClassId.CASH, 1_100_000),
            Asset(Month("2026-02"), AccountId.DC, AssetClassId.PENSION, 550_000),
        ],
        markets=[],
        accounts=accounts,
        cashflows=cashflows,
    )

    assert cashflows[0].net_savings == 100_000
    assert cashflows[0].asset_contribution == 50_000
    assert cashflows[0].net_worth_contribution == 150_000
    assert balance_sheets[1].investment_gain_loss == 0


def test_savings_rate_uses_cash_savings_not_asset_contribution() -> None:
    metrics = MetricsCalculator().calculate(
        cf_statements=[
            CashFlowStatement(
                month=Month("2026-01"),
                after_tax_income=100_000,
                expenditure=40_000,
                net_savings=60_000,
                asset_contribution=40_000,
            )
        ],
        bs_statements=[
            BalanceSheet(
                month=Month("2026-01"),
                liquid_assets=60_000,
                risk_assets=0,
                pension_assets=40_000,
                total_financial_assets=100_000,
                investment_gain_loss=0,
            )
        ],
        markets=[],
    )

    assert metrics[0].savings_rate == 0.6
