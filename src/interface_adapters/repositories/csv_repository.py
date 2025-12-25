import pandas as pd
from typing import List
from src.domain.entities.models import (
    Income,
    Expense,
    Asset,
    Market,
    Account,
    PaymentMethod,
)
from src.constants import AccountId, PaymentMethodId, AssetClassId, AccountType, Currency
from src.domain.repositories.interfaces import (
    ITransactionRepository,
    IAssetRepository,
    IMarketRepository,
    IMasterRepository,
)


class CsvTransactionRepository(ITransactionRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_incomes(self) -> List[Income]:
        df = pd.read_csv(f"{self.data_dir}/data/input/income.csv")
        return [
            Income(
                month=row["month"], account_id=AccountId(row["account_id"]), amount=row["amount"]
            )
            for _, row in df.iterrows()
        ]

    def get_expenses(self) -> List[Expense]:
        df = pd.read_csv(f"{self.data_dir}/data/input/expense.csv")
        return [
            Expense(
                month=row["month"], method_id=PaymentMethodId(row["method_id"]), amount=row["amount"]
            )
            for _, row in df.iterrows()
        ]


class CsvAssetRepository(IAssetRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_assets(self) -> List[Asset]:
        df = pd.read_csv(f"{self.data_dir}/data/input/assets.csv")
        return [
            Asset(
                month=row["month"],
                account_id=AccountId(row["account_id"]),
                asset_class=AssetClassId(row["asset_class"]),
                balance=float(row["balance"]),
            )
            for _, row in df.iterrows()
        ]


class CsvMarketRepository(IMarketRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_market_data(self) -> List[Market]:
        df = pd.read_csv(f"{self.data_dir}/data/input/market.csv")
        return [
            Market(
                month=row["month"],
                usd_jpy=float(row["usd_jpy"]),
                eur_jpy=float(row["eur_jpy"]),
                sp500=float(row["sp500"]),
            )
            for _, row in df.iterrows()
        ]


class CsvMasterRepository(IMasterRepository):
    def __init__(self, key_dir: str):
        self.data_dir = key_dir

    def get_accounts(self) -> List[Account]:
        df = pd.read_csv(f"{self.data_dir}/master/accounts.csv")
        return [
            Account(
                id=AccountId(row["account_id"]),
                name=row["name"],
                type=AccountType(row["type"]),
                currency=Currency(row["currency"]),
                risk=int(row["risk"]),
            )
            for _, row in df.iterrows()
        ]

    def get_payment_methods(self) -> List[PaymentMethod]:
        df = pd.read_csv(f"{self.data_dir}/master/payment_methods.csv")
        return [
            PaymentMethod(
                id=PaymentMethodId(row["method_id"]),
                name=row["name"],
                settlement_account=AccountId(row["settlement_account"]) if pd.notna(row["settlement_account"]) else None,
            )
            for _, row in df.iterrows()
        ]
