from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AccountType(StrEnum):
    BANK = "bank"
    SECURITIES = "securities"
    FINTECH = "fintech"
    CRYPTO = "crypto"
    PENSION = "pension"


class AssetKind(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    FUND = "fund"
    BOND = "bond"
    CRYPTO = "crypto"
    PENSION = "pension"
    FX = "fx"


class Institution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")


class Account(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    institution_id: str
    account_type: AccountType
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$")
    kind: AssetKind
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Holding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    asset_id: str
    quantity: Decimal = Field(gt=0)
    acquisition_cost: Decimal | None = Field(default=None, ge=0)


class TransactionKind(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    DIVIDEND = "dividend"
    DISTRIBUTION = "distribution"
    INTEREST = "interest"
    FEE = "fee"


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    account_id: str
    kind: TransactionKind
    booked_on: date
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    asset_id: str | None = None
    counterparty_account_id: str | None = None


class Valuation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    asset_id: str
    value: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    valuation_date: date
    source_revision: str = Field(min_length=1, max_length=200)


class BalanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    balance: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    balance_date: date
    source_revision: str = Field(min_length=1, max_length=200)


class AssetLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institutions: list[Institution]
    accounts: list[Account]
    assets: list[Asset]
    holdings: list[Holding] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)
    valuations: list[Valuation] = Field(default_factory=list)
    balance_snapshots: list[BalanceSnapshot] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references_and_duplicates(self) -> AssetLedger:
        institution_ids = [item.institution_id for item in self.institutions]
        account_ids = [item.account_id for item in self.accounts]
        asset_ids = [item.asset_id for item in self.assets]
        if len(institution_ids) != len(set(institution_ids)):
            raise ValueError("duplicate institution_id")
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("duplicate account_id")
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("duplicate asset_id")

        institution_set = set(institution_ids)
        account_set = set(account_ids)
        asset_set = set(asset_ids)
        for account in self.accounts:
            if account.institution_id not in institution_set:
                raise ValueError("account references unknown institution")
        for holding in self.holdings:
            if holding.account_id not in account_set or holding.asset_id not in asset_set:
                raise ValueError("holding references unknown account or asset")
        for transaction in self.transactions:
            if transaction.account_id not in account_set:
                raise ValueError("transaction references unknown account")
            if transaction.asset_id is not None and transaction.asset_id not in asset_set:
                raise ValueError("transaction references unknown asset")
            if (
                transaction.counterparty_account_id is not None
                and transaction.counterparty_account_id not in account_set
            ):
                raise ValueError("transaction references unknown counterparty account")
        return self


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date
    currency: str
    subtotals: dict[AccountType, Decimal | None]
    total_assets: Decimal | None
    problems: list[str]


def reconcile_asset_ledger(
    ledger: AssetLedger, *, as_of: date, currency: str = "JPY"
) -> ReconciliationResult:
    """Reconcile account cash and holdings without coercing missing data to zero.

    Cash/deposit balances are represented only by BalanceSnapshot. Investment positions
    are represented by Holding + Valuation. A subtotal becomes unknown when any account
    in that class lacks an as-of balance or any holding lacks a matching valuation.
    Cross-currency conversion is intentionally not inferred here.
    """

    accounts = {item.account_id: item for item in ledger.accounts}
    balances = {(item.account_id, item.balance_date): item for item in ledger.balance_snapshots}
    valuations = {
        (item.account_id, item.asset_id, item.valuation_date): item
        for item in ledger.valuations
    }
    account_values: dict[str, Decimal] = defaultdict(Decimal)
    invalid_accounts: set[str] = set()
    problems: list[str] = []

    for account_id in accounts:
        snapshot = balances.get((account_id, as_of))
        if snapshot is None:
            problems.append(f"missing balance_snapshot: {account_id} @ {as_of.isoformat()}")
            invalid_accounts.add(account_id)
        elif snapshot.currency != currency:
            problems.append(f"currency conversion required for balance_snapshot: {account_id}")
            invalid_accounts.add(account_id)
        else:
            account_values[account_id] += snapshot.balance

    for holding in ledger.holdings:
        valuation = valuations.get((holding.account_id, holding.asset_id, as_of))
        if valuation is None:
            problems.append(
                f"missing valuation: {holding.account_id}/{holding.asset_id} @ {as_of.isoformat()}"
            )
            invalid_accounts.add(holding.account_id)
        elif valuation.currency != currency:
            problems.append(
                f"currency conversion required for valuation: {holding.account_id}/{holding.asset_id}"
            )
            invalid_accounts.add(holding.account_id)
        else:
            account_values[holding.account_id] += valuation.value

    subtotals: dict[AccountType, Decimal | None] = {}
    for account_type in AccountType:
        members = [item for item in ledger.accounts if item.account_type == account_type]
        if any(item.account_id in invalid_accounts for item in members):
            subtotals[account_type] = None
        else:
            subtotals[account_type] = sum(
                (account_values[item.account_id] for item in members), Decimal(0)
            )

    known = list(subtotals.values())
    total_assets = None if any(value is None for value in known) else sum(known, Decimal(0))
    return ReconciliationResult(
        as_of=as_of,
        currency=currency,
        subtotals=subtotals,
        total_assets=total_assets,
        problems=problems,
    )
