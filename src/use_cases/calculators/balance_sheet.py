from typing import List, Dict
from collections import defaultdict
from src.domain.entities.models import Asset, Market, Account, Month
from src.constants import AccountType, Currency
from src.use_cases.dtos.output import BalanceSheet, CashFlowStatement


class BalanceSheetCalculator:
    def calculate(
        self,
        assets: List[Asset],
        markets: List[Market],
        accounts: List[Account],
        cashflows: List[CashFlowStatement],
    ) -> List[BalanceSheet]:
        account_map: Dict[str, Account] = {acc.id: acc for acc in accounts}

        market_map: Dict[str, Market] = {m.month: m for m in markets}

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
            market = market_map.get(month)
            if not market:
                pass

            liquid_total = 0.0
            risk_total = 0.0
            pension_total = 0.0

            for asset in current_assets:
                acc = account_map.get(asset.account_id)
                if not acc:
                    continue

                rate = 1.0
                if acc.currency == Currency.USD:
                    rate = market.usd_jpy if market else 1.0
                elif acc.currency == Currency.EUR:
                    rate = market.eur_jpy if market else 1.0

                jpy_balance = asset.balance * rate

                jpy_balance = asset.balance * rate

                if acc.type == AccountType.PENSION:
                    pension_total += jpy_balance
                elif acc.risk == 1:
                    risk_total += jpy_balance
                else:
                    liquid_total += jpy_balance

            total_assets = liquid_total + risk_total + pension_total

            total_assets = liquid_total + risk_total + pension_total

            cf = cf_map.get(month)
            net_savings = cf.net_savings if cf else 0.0

            if not bs_list:
                investment_gain = 0.0
            else:
                investment_gain = total_assets - (prev_total_assets + net_savings)

            bs_list.append(
                BalanceSheet(
                    month=Month(month),
                    liquid_assets=int(liquid_total),
                    risk_assets=int(risk_total),
                    pension_assets=int(pension_total),
                    total_financial_assets=int(total_assets),
                    investment_gain_loss=int(investment_gain),
                )
            )

            prev_total_assets = total_assets

        return bs_list
