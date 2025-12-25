from abc import ABC, abstractmethod
from typing import List
from src.domain.entities.models import (
    Income,
    Expense,
    Asset,
    Market,
    Account,
    PaymentMethod,
)


class ITransactionRepository(ABC):
    @abstractmethod
    def get_incomes(self) -> List[Income]:
        pass

    @abstractmethod
    def get_expenses(self) -> List[Expense]:
        pass


class IAssetRepository(ABC):
    @abstractmethod
    def get_assets(self) -> List[Asset]:
        pass


class IMarketRepository(ABC):
    @abstractmethod
    def get_market_data(self) -> List[Market]:
        pass


class IMasterRepository(ABC):
    @abstractmethod
    def get_accounts(self) -> List[Account]:
        pass

    @abstractmethod
    def get_payment_methods(self) -> List[PaymentMethod]:
        pass
