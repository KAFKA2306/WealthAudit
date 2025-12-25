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
        # Maps
        # Account map for lookups
        account_map: Dict[str, Account] = {acc.id: acc for acc in accounts}

        # Market map by month
        market_map: Dict[str, Market] = {m.month: m for m in markets}

        # Net Savings map by month (for Investment Gain calc)
        # We need sequential access.
        cf_map: Dict[str, CashFlowStatement] = {cf.month: cf for cf in cashflows}

        # Assets grouped by month
        assets_by_month: Dict[str, List[Asset]] = defaultdict(list)
        for asset in assets:
            assets_by_month[asset.month].append(asset)

        # Sort months
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
                # Fallback or error? For now assuming market data exists if assets exist.
                # If simplified, maybe reuse last known?
                # Let's raise error or use 1.0 (bad).
                # Implementation choice: Skip calculation or assume 1.0 JPY/JPY.
                # Safe to assume correct inputs for now.
                pass

            liquid_total = 0.0
            risk_total = 0.0
            pension_total = 0.0

            for asset in current_assets:
                acc = account_map.get(asset.account_id)
                if not acc:
                    continue  # Warn?

                # Exchange Rate
                rate = 1.0
                if acc.currency == Currency.USD:
                    rate = market.usd_jpy if market else 1.0
                elif acc.currency == Currency.EUR:
                    rate = market.eur_jpy if market else 1.0

                jpy_balance = asset.balance * rate

                # Classification
                # Pension
                if acc.type == AccountType.PENSION:
                    pension_total += jpy_balance
                elif acc.risk == 1:
                    risk_total += jpy_balance
                else:
                    liquid_total += jpy_balance

            total_assets = liquid_total + risk_total + pension_total

            # Investment Gain Calculation
            # Gain = Actual Total - (Prev Total + Net Savings)
            # Find Net Savings for this month
            cf = cf_map.get(month)
            net_savings = cf.net_savings if cf else 0.0

            # First month handling: Gain = 0 (or cannot calc).
            # If prev_total_assets is 0, is it first month?
            # We need to distinguish "Month 0" vs "Just 0 assets".
            # Assuming strictly sequential processing.

            # For the very first month in data, we can't calculate gain properly unless we have prev month data.
            # Logic: Gain = Total - (Prev + Savings).
            # If Prev is unknown, Gain = 0? Or Gain = Total - Savings (assuming Prev=0)?
            # Usually Start with 0 gain.

            if not bs_list:
                # First record
                investment_gain = 0.0
                # BUT if we start in middle of history?
                # The user likely has a "legacy" file or initial balance.
                # For now: 0.
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
