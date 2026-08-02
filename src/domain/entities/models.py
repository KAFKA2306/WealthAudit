from dataclasses import dataclass
from typing import NewType, Optional

from src.constants import (
    AccountId,
    AssetClassId,
    PaymentMethodId,
    AccountType,
    Currency,
)

Month = NewType("Month", str)


@dataclass(frozen=True)
class Income:
    month: Month
    account_id: AccountId
    amount: int


@dataclass(frozen=True)
class Expense:
    month: Month
    method_id: PaymentMethodId
    amount: int


@dataclass(frozen=True, init=False)
class Asset:
    month: Month
    account_id: AccountId
    asset_class: AssetClassId
    native_balance: float
    native_currency: Optional[Currency]

    def __init__(
        self,
        month: Month,
        account_id: AccountId,
        asset_class: AssetClassId,
        balance: float | None = None,
        native_balance: float | None = None,
        currency: Currency | None = None,
        native_currency: Currency | None = None,
    ) -> None:
        resolved_balance = native_balance if native_balance is not None else balance
        if resolved_balance is None:
            raise ValueError("Asset requires balance or native_balance")
        resolved_currency = (
            native_currency if native_currency is not None else currency
        )
        object.__setattr__(self, "month", month)
        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "asset_class", asset_class)
        object.__setattr__(self, "native_balance", float(resolved_balance))
        object.__setattr__(self, "native_currency", resolved_currency)

    @property
    def balance(self) -> float:
        """Backward-compatible alias for the native-currency balance."""
        return self.native_balance


@dataclass(frozen=True)
class AssetValuation:
    month: Month
    account_id: AccountId
    asset_class: AssetClassId
    native_currency: Currency
    native_balance: float
    fx_rate_to_jpy: float
    jpy_value: float


@dataclass(frozen=True)
class Market:
    month: Month
    usd_jpy: float
    eur_jpy: float
    sp500: float


@dataclass(frozen=True)
class Account:
    id: AccountId
    name: str
    type: AccountType
    currency: Currency
    risk: int


@dataclass(frozen=True)
class AssetClass:
    id: AssetClassId
    name: str
    risk_level: int


@dataclass(frozen=True)
class PaymentMethod:
    id: PaymentMethodId
    name: str
    settlement_account: Optional[AccountId]
