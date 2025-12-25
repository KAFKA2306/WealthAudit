from injector import Module, provider, singleton
from src.domain.repositories.interfaces import (
    ITransactionRepository,
    IAssetRepository,
    IMarketRepository,
    IMasterRepository,
)
from src.interface_adapters.repositories.csv_repository import (
    CsvTransactionRepository,
    CsvAssetRepository,
    CsvMarketRepository,
    CsvMasterRepository,
)
from src.use_cases.calculators.cash_flow import CashFlowCalculator
from src.use_cases.calculators.balance_sheet import BalanceSheetCalculator
from src.use_cases.calculators.metrics import MetricsCalculator


class AppModule(Module):
    def __init__(self, key_dir: str):
        self.key_dir = key_dir

    @singleton
    @provider
    def provide_transaction_repository(self) -> ITransactionRepository:
        return CsvTransactionRepository(self.key_dir)

    @singleton
    @provider
    def provide_asset_repository(self) -> IAssetRepository:
        return CsvAssetRepository(self.key_dir)

    @singleton
    @provider
    def provide_market_repository(self) -> IMarketRepository:
        return CsvMarketRepository(self.key_dir)

    @singleton
    @provider
    def provide_master_repository(self) -> IMasterRepository:
        return CsvMasterRepository(self.key_dir)

    @singleton
    @provider
    def provide_cash_flow_calculator(self) -> CashFlowCalculator:
        return CashFlowCalculator()

    @singleton
    @provider
    def provide_balance_sheet_calculator(self) -> BalanceSheetCalculator:
        return BalanceSheetCalculator()

    @singleton
    @provider
    def provide_metrics_calculator(self) -> MetricsCalculator:
        return MetricsCalculator()
