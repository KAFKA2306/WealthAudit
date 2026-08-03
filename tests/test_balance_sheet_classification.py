import pytest

from src.constants import AccountId, AccountType, AssetClassId, Currency
from src.domain.entities.models import Account, Asset, AssetClass, Market, Month
from src.use_cases.calculators.balance_sheet import BalanceSheetCalculator


def _account(
    account_id: AccountId,
    account_type: AccountType,
    currency: Currency = Currency.JPY,
    risk: int = 0,
) -> Account:
    return Account(
        id=account_id,
        name=account_id.value,
        type=account_type,
        currency=currency,
        risk=risk,
    )


def _asset_class(asset_class: AssetClassId, risk_level: int) -> AssetClass:
    return AssetClass(
        id=asset_class,
        name=asset_class.value,
        risk_level=risk_level,
    )


def test_balance_sheet_prefers_asset_class_risk_level_over_account_risk() -> None:
    result = BalanceSheetCalculator().calculate(
        assets=[
            Asset(Month("2026-01"), AccountId.SBI_SEC, AssetClassId.CASH, 100),
            Asset(Month("2026-01"), AccountId.YUCHO, AssetClassId.FUND, 200),
            Asset(Month("2026-01"), AccountId.YUCHO, AssetClassId.STOCK_US, 300),
            Asset(Month("2026-01"), AccountId.YUCHO, AssetClassId.PENSION, 400),
        ],
        markets=[],
        accounts=[
            _account(AccountId.SBI_SEC, AccountType.SECURITIES, risk=1),
            _account(AccountId.YUCHO, AccountType.BANK, risk=0),
        ],
        cashflows=[],
        asset_classes=[
            _asset_class(AssetClassId.CASH, 0),
            _asset_class(AssetClassId.FUND, 1),
            _asset_class(AssetClassId.STOCK_US, 1),
            _asset_class(AssetClassId.PENSION, 0),
        ],
    )

    assert result[0].liquid_assets == 100
    assert result[0].risk_assets == 500
    assert result[0].pension_assets == 400
    assert result[0].total_financial_assets == 1000


def test_balance_sheet_uses_latest_prior_market_for_missing_months() -> None:
    result = BalanceSheetCalculator().calculate(
        assets=[
            Asset(Month("2026-01"), AccountId.DEUTSCHE, AssetClassId.CASH, 10),
            Asset(Month("2026-03"), AccountId.DEUTSCHE, AssetClassId.CASH, 10),
            Asset(Month("2026-05"), AccountId.DEUTSCHE, AssetClassId.CASH, 10),
        ],
        markets=[
            Market(Month("2025-12"), usd_jpy=150, eur_jpy=160, sp500=5000),
            Market(Month("2026-04"), usd_jpy=170, eur_jpy=180, sp500=5100),
        ],
        accounts=[
            _account(AccountId.DEUTSCHE, AccountType.BANK, Currency.USD),
        ],
        cashflows=[],
        asset_classes=[
            _asset_class(AssetClassId.CASH, 0),
        ],
    )

    assert [bs.month for bs in result] == [
        Month("2026-01"),
        Month("2026-03"),
        Month("2026-05"),
    ]
    assert [bs.liquid_assets for bs in result] == [1500, 1500, 1700]


def test_balance_sheet_raises_for_foreign_currency_without_market_data() -> None:
    with pytest.raises(ValueError, match="Market data is required to convert USD asset"):
        BalanceSheetCalculator().calculate(
            assets=[
                Asset(Month("2026-01"), AccountId.DEUTSCHE, AssetClassId.CASH, 10),
            ],
            markets=[],
            accounts=[
                _account(AccountId.DEUTSCHE, AccountType.BANK, Currency.USD),
            ],
            cashflows=[],
            asset_classes=[
                _asset_class(AssetClassId.CASH, 0),
            ],
        )
