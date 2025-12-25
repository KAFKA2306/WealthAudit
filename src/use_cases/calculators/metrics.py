from datetime import datetime
from typing import List, Optional, Tuple
from src.domain.entities.models import Market, Month
from src.use_cases.dtos.output import BalanceSheet, CashFlowStatement, FinancialMetrics


class MetricsCalculator:
    def calculate(
        self,
        cf_statements: List[CashFlowStatement],
        bs_statements: List[BalanceSheet],
        markets: List[Market],
    ) -> List[FinancialMetrics]:
        cf_map = {cf.month: cf for cf in cf_statements}
        bs_map = {bs.month: bs for bs in bs_statements}
        market_map = {m.month: m for m in markets}

        months = sorted(list(set(cf_map.keys()) | set(bs_map.keys()) | set(market_map.keys())))

        # Helper to get past N months (inclusive of current)
        def get_past_n_months_sums(
            current_month_str: str, n: int
        ) -> Tuple[int, int]:
            curr_date = datetime.strptime(current_month_str, "%Y-%m")
            curr_y = curr_date.year
            curr_m = curr_date.month
            
            total_gain = 0
            total_expense = 0
            
            for i in range(n):
                # Calculate target year/month
                # total_months_idx = y * 12 + (m - 1)
                month_idx = curr_y * 12 + (curr_m - 1) - i
                y = month_idx // 12
                m = (month_idx % 12) + 1
                
                m_str = f"{y:04d}-{m:02d}"
                
                bs_item = bs_map.get(m_str)
                cf_item = cf_map.get(m_str)
                
                if bs_item:
                    total_gain += bs_item.investment_gain_loss
                if cf_item:
                    total_expense += cf_item.expenditure
            
            return total_gain, total_expense

        metrics_list: List[FinancialMetrics] = []

        prev_bs: Optional[BalanceSheet] = None
        prev_market: Optional[Market] = None

        for month in months:
            cf = cf_map.get(month)
            bs = bs_map.get(month)
            market = market_map.get(month)

            if not cf or not bs:
                # Need both to calc structure metrics
                continue

            # 1. Savings Rate
            # savings_rate = net_savings / after_tax_income
            savings_rate = 0.0
            if cf.after_tax_income != 0:
                savings_rate = cf.net_savings / cf.after_tax_income

            # 2. Risk Asset Ratio
            # risk_asset_ratio = risk_assets / total_financial_assets
            equity_ratio = 0.0
            if bs.total_financial_assets != 0:
                equity_ratio = bs.risk_assets / bs.total_financial_assets

            # 3. Monthly Return (ROI)
            # monthly_return = investment_gain / prev_month_risk_assets
            monthly_return = 0.0
            prev_risk_assets = 0
            if prev_bs:
                prev_risk_assets = prev_bs.risk_assets
                if prev_risk_assets > 0:
                    monthly_return = bs.investment_gain_loss / prev_risk_assets

            # 4. Monthly Alpha & Benchmark Return
            # alpha = monthly_return - benchmark_return
            # Benchmark Return = (JPY_SP500_M / JPY_SP500_M-1) - 1
            monthly_alpha = 0.0
            benchmark_return = 0.0
            
            if market and prev_market:
                # Calculate JPY denominated SP500 for both months
                current_sp500_jpy = market.sp500 * market.usd_jpy
                prev_sp500_jpy = prev_market.sp500 * prev_market.usd_jpy

                if prev_sp500_jpy > 0:
                    benchmark_return = (current_sp500_jpy / prev_sp500_jpy) - 1
                    monthly_alpha = monthly_return - benchmark_return

            # 5. FI Ratios
            # Trailing 12-Month FI Ratio
            gain_12m, xp_12m = get_past_n_months_sums(month, 12)
            fi_ratio_12m = 0.0
            if xp_12m != 0:
                fi_ratio_12m = gain_12m / xp_12m

            # Trailing 48-Month FI Ratio
            gain_48m, xp_48m = get_past_n_months_sums(month, 48)
            fi_ratio_48m = 0.0
            if xp_48m != 0:
                fi_ratio_48m = gain_48m / xp_48m

            # Forward 12-Month FI Ratio (Projected)
            # fi_ratio_next_12m = (risk_assets * expected_annual_return) / projected_annual_expenses
            # projected_annual_expenses = trailing 12-month expenses (xp_12m)
            expected_annual_return = 0.05  # Assumption: 5% annual return
            fi_ratio_next_12m = 0.0
            if xp_12m != 0:
                fi_ratio_next_12m = (bs.risk_assets * expected_annual_return) / xp_12m

            metrics_list.append(
                FinancialMetrics(
                    month=Month(month),
                    savings_rate=savings_rate,
                    risk_asset_ratio=equity_ratio,
                    monthly_return=monthly_return,
                    monthly_alpha=monthly_alpha,
                    benchmark_return=benchmark_return,
                    fi_ratio_12m=fi_ratio_12m,
                    fi_ratio_48m=fi_ratio_48m,
                    fi_ratio_next_12m=fi_ratio_next_12m,
                )
            )

            # Update history for next iteration
            # We ONLY update if we had valid BS/Market for this month
            if bs:
                prev_bs = bs
            if market:
                prev_market = market

        return metrics_list
