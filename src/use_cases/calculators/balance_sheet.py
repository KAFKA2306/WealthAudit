from bisect import bisect_right
from typing import List, Dict, Optional, Sequence
from collections import defaultdict
from src.domain.entities.models import Asset, Market, Account, AssetClass, Month
from src.constants import AccountId, AccountType, AssetClassId, Currency
from src.use_cases.dtos.output import BalanceSheet, CashFlowStatement
from src.utils.months import month_end_label


class BalanceSheetCalculator:
    def calculate(
        self,
        assets: List[Asset],
        markets: List[Market],
        accounts: List[Account],
        cashflows: List[CashFlowStatement],
        asset_classes: Optional[List[AssetClass]] = None,
    ) -> List[BalanceSheet]:
        account_map: Dict[AccountId, Account] = {acc.id: acc for acc in accounts}
        asset_class_map: Dict[AssetClassId, AssetClass] = {
            asset_class.id: asset_class for asset_class in asset_classes or []
        }

        market_map: Dict[str, Market] = {m.month: m for m in markets}
        market_cache = sorted(markets, key=lambda m: m.month)
        market_months = [m.month for m in market_cache]

        cf_map: Dict[str, CashFlowStatement] = {cf.month: cf for cf in cashflows}

        assets_by_month: Dict[str, List[Asset]] = defaultdict(list)
        for asset in assets:
            assets_by_month[asset.month].append(asset)

        sorted_months = sorted(
            list(set(assets_by_month.keys()) | set(market_map.keys()))
        )

        bs_list: List[BalanceSheet] = []
        prev_total_assets = 0.0

        for month in sorted_months:
            if month not in assets_by_month:
                continue

            current_assets = assets_by_month[month]
            market = self._market_for_month(month, market_cache, market_months)
            month_label = month_end_label(month)

            liquid_total = 0.0
            risk_total = 0.0
            pension_total = 0.0

            for asset in current_assets:
                acc = account_map.get(asset.account_id)
                if not acc:
                    continue

                rate = self._conversion_rate(asset, acc, market, bool(market_cache))
                jpy_balance = asset.balance * rate

                asset_class = asset_class_map.get(asset.asset_class)
                if (
                    acc.type == AccountType.PENSION
                    or asset.asset_class == AssetClassId.PENSION
                ):
                    pension_total += jpy_balance
                elif asset_class and asset_class.risk_level == 1:
                    risk_total += jpy_balance
                elif asset_class and asset_class.risk_level == 0:
                    liquid_total += jpy_balance
                elif acc.risk == 1:
                    risk_total += jpy_balance
                else:
                    liquid_total += jpy_balance

            total_assets = liquid_total + risk_total + pension_total

            cf = cf_map.get(month_label)
            net_worth_contribution = cf.net_worth_contribution if cf else 0.0

            if not bs_list:
                investment_gain = 0.0
            else:
                investment_gain = (
                    total_assets - prev_total_assets - net_worth_contribution
                )

            bs_list.append(
                BalanceSheet(
                    month=Month(month_label),
                    liquid_assets=int(liquid_total),
                    risk_assets=int(risk_total),
                    pension_assets=int(pension_total),
                    total_financial_assets=int(total_assets),
                    investment_gain_loss=int(investment_gain),
                )
            )

            prev_total_assets = total_assets

        return bs_list

    def _market_for_month(
        self,
        month: str,
        market_cache: List[Market],
        market_months: Sequence[str],
    ) -> Optional[Market]:
        if not market_cache:
            return None

        prior_index = bisect_right(market_months, month) - 1
        if prior_index >= 0:
            return market_cache[prior_index]
        return market_cache[0]

    def _conversion_rate(
        self,
        asset: Asset,
        account: Account,
        market: Optional[Market],
        has_market_data: bool,
    ) -> float:
        if account.currency in (Currency.JPY, Currency.MULTI):
            return 1.0

        if not has_market_data or market is None:
            raise ValueError(
                "Market data is required to convert "
                f"{account.currency.value} asset "
                f"{asset.account_id.value}/{asset.asset_class.value} "
                f"in {asset.month}."
            )

        if account.currency == Currency.USD:
            return market.usd_jpy
        if account.currency == Currency.EUR:
            return market.eur_jpy

        raise ValueError(
            f"Unsupported foreign currency {account.currency.value} "
            f"for {asset.account_id.value}/{asset.asset_class.value}."
        )
