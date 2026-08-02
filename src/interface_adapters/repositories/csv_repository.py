from __future__ import annotations

from typing import List

import pandas as pd

from src.constants import (
    AccountId,
    AccountType,
    AssetClassId,
    Currency,
    PaymentMethodId,
)
from src.domain.entities.models import (
    Account,
    Asset,
    AssetClass,
    Expense,
    Income,
    Market,
    PaymentMethod,
)
from src.domain.repositories.interfaces import (
    IAssetRepository,
    IMarketRepository,
    IMasterRepository,
    ITransactionRepository,
)


def _optional_currency(row: pd.Series) -> Currency | None:
    for column in ("native_currency", "currency"):
        if column in row.index and pd.notna(row[column]) and str(row[column]).strip():
            return Currency(str(row[column]).strip())
    return None


def _native_balance(row: pd.Series) -> float:
    for column in ("native_balance", "balance"):
        if column in row.index and pd.notna(row[column]):
            return float(row[column])
    raise ValueError("assets.csv requires native_balance or balance")


class CsvTransactionRepository(ITransactionRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_incomes(self) -> List[Income]:
        frame = pd.read_csv(f"{self.data_dir}/data/input/income.csv")
        return [
            Income(
                month=row["month"],
                account_id=AccountId(row["account_id"]),
                amount=int(row["amount"]),
            )
            for _, row in frame.iterrows()
        ]

    def get_expenses(self) -> List[Expense]:
        frame = pd.read_csv(f"{self.data_dir}/data/input/expense.csv")
        return [
            Expense(
                month=row["month"],
                method_id=PaymentMethodId(row["method_id"]),
                amount=int(row["amount"]),
            )
            for _, row in frame.iterrows()
        ]


class CsvAssetRepository(IAssetRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_assets(self) -> List[Asset]:
        frame = pd.read_csv(f"{self.data_dir}/data/input/assets.csv")
        return [
            Asset(
                month=row["month"],
                account_id=AccountId(row["account_id"]),
                asset_class=AssetClassId(row["asset_class"]),
                native_balance=_native_balance(row),
                native_currency=_optional_currency(row),
            )
            for _, row in frame.iterrows()
        ]


class CsvMarketRepository(IMarketRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_market_data(self) -> List[Market]:
        frame = pd.read_csv(f"{self.data_dir}/data/input/market.csv")
        return [
            Market(
                month=row["month"],
                usd_jpy=float(row["usd_jpy"]),
                eur_jpy=float(row["eur_jpy"]),
                sp500=float(row["sp500"]),
            )
            for _, row in frame.iterrows()
        ]


class CsvMasterRepository(IMasterRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_accounts(self) -> List[Account]:
        frame = pd.read_csv(f"{self.data_dir}/master/accounts.csv")
        return [
            Account(
                id=AccountId(row["account_id"]),
                name=str(row["name"]),
                type=AccountType(row["type"]),
                currency=Currency(row["currency"]),
                risk=int(row["risk"]),
            )
            for _, row in frame.iterrows()
        ]

    def get_asset_classes(self) -> List[AssetClass]:
        frame = pd.read_csv(f"{self.data_dir}/master/asset_classes.csv")
        return [
            AssetClass(
                id=AssetClassId(row["class_id"]),
                name=str(row["name"]),
                risk_level=int(row["risk_level"]),
            )
            for _, row in frame.iterrows()
        ]

    def get_payment_methods(self) -> List[PaymentMethod]:
        frame = pd.read_csv(f"{self.data_dir}/master/payment_methods.csv")
        return [
            PaymentMethod(
                id=PaymentMethodId(row["method_id"]),
                name=str(row["name"]),
                settlement_account=(
                    AccountId(row["settlement_account"])
                    if pd.notna(row.get("settlement_account"))
                    else None
                ),
            )
            for _, row in frame.iterrows()
        ]
