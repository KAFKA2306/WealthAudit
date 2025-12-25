from dataclasses import dataclass
from typing import NewType, Optional

# Value Objects / Type Aliases
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
    amount: int  # JPY


@dataclass(frozen=True)
class Expense:
    month: Month
    method_id: PaymentMethodId
    amount: int  # JPY (Negative for adjustments)


@dataclass(frozen=True)
class Asset:
    month: Month
    account_id: AccountId
    asset_class: AssetClassId
    balance: float  # Original Currency


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
    type: AccountType  # 'bank', 'securities', etc.
    currency: Currency  # 'JPY', 'EUR', 'multi'
    risk: int  # 0 or 1


@dataclass(frozen=True)
class PaymentMethod:
    id: PaymentMethodId
    name: str
    settlement_account: Optional[AccountId]  # Link to Account
