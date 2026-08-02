from collections import defaultdict
from typing import Dict, List, Optional

from src.constants import AccountId, AccountType, AssetClassId
from src.domain.entities.models import Account, Asset, AssetClass, Market, Month
from src.use_cases.dtos.output import BalanceSheet, CashFlowStatement
from src.use_cases.valuation import is_consecutive_month, value_assets


class BalanceSheetCalculator:
    def calculate(
        self,
        assets: List[Asset],
        markets: List[Market],
        accounts: List[Account],
        cashflows: List[CashFlowStatement],
        asset_classes: Optional[List[AssetClass]] = None,
    ) -> List[BalanceSheet]:
        account_map: Dict[AccountId, Account] = {
            account.id: account for account in accounts
        }
        class_map = {
            asset_class.id: asset_class for asset_class in asset_classes or []
        }
        cf_map = {str(statement.month): statement for statement in cashflows}

        assets_by_month: dict[str, list[Asset]] = defaultdict(list)
        for asset in assets:
            assets_by_month[str(asset.month)].append(asset)

        statements: list[BalanceSheet] = []
        previous_statement: BalanceSheet | None = None

        for month in sorted(assets_by_month):
            valuations = value_assets(assets_by_month[month], markets, accounts)
            liquid_total = 0.0
            risk_total = 0.0
            pension_total = 0.0

            for valuation in valuations:
                account = account_map[valuation.account_id]
                asset_class = class_map.get(valuation.asset_class)
                if (
                    account.type == AccountType.PENSION
                    or valuation.asset_class == AssetClassId.PENSION
                ):
                    pension_total += valuation.jpy_value
                elif asset_class is not None:
                    if asset_class.risk_level == 1:
                        risk_total += valuation.jpy_value
                    else:
                        liquid_total += valuation.jpy_value
                elif account.risk == 1:
                    risk_total += valuation.jpy_value
                else:
                    liquid_total += valuation.jpy_value

            total_assets = liquid_total + risk_total + pension_total
            cashflow = cf_map.get(month)
            contribution = cashflow.net_worth_contribution if cashflow else 0

            gain = 0.0
            return_base_assets = 0.0
            if previous_statement is not None and is_consecutive_month(
                str(previous_statement.month), month
            ):
                gain = (
                    total_assets
                    - previous_statement.total_financial_assets
                    - contribution
                )
                return_base_assets = (
                    previous_statement.risk_assets
                    + previous_statement.pension_assets
                )

            statement = BalanceSheet(
                month=Month(month),
                liquid_assets=round(liquid_total),
                risk_assets=round(risk_total),
                pension_assets=round(pension_total),
                total_financial_assets=round(total_assets),
                investment_gain_loss=round(gain),
                return_base_assets=round(return_base_assets),
            )
            statements.append(statement)
            previous_statement = statement

        return statements
