# Financial Metrics Logic

This document describes the logic for calculating financial metrics. The calculations are performed by the `MetricsCalculator`.

## Savings Rate
The savings rate is the ratio of net savings to after-tax income.

`savings_rate = net_savings / after_tax_income`

## Risk Asset Ratio
The risk asset ratio is the ratio of risk assets to total financial assets.

`risk_asset_ratio = risk_assets / total_financial_assets`

## Monthly Return (ROI)
The monthly return on investment is the ratio of investment gain/loss to the previous month's risk assets.

`monthly_return = investment_gain_loss / prev_month_risk_assets`

## Monthly Alpha
The monthly alpha is the excess return of the investment compared to a benchmark. The benchmark used is the S&P 500 index, converted to JPY.

`monthly_alpha = monthly_return - benchmark_return`

where `benchmark_return` is the monthly return of the JPY-denominated S&P 500 index.

## Benchmark Return
The benchmark return is the monthly return of the S&P 500 index converted to JPY.

`benchmark_return = (sp500_jpy_current - sp500_jpy_prev) / sp500_jpy_prev`

This calculation accounts for both the index performance and the USD/JPY exchange rate movement.

## Financial Independence Ratio (FI Ratio)
The Financial Independence Ratio measures how many months of expenses can be covered by investment income (passive income). A ratio of 1.0 or higher indicates that passive income fully covers expenses.

### Trailing 12-Month FI Ratio
The FI ratio based on the past 12 months of data.

`fi_ratio_12m = sum(investment_gain_loss, 12m) / sum(expenses, 12m)`

### Trailing 48-Month FI Ratio
The FI ratio based on the past 48 months (4 years) of data. This provides a longer-term, more stable view.

`fi_ratio_48m = sum(investment_gain_loss, 48m) / sum(expenses, 48m)`

### Forward 12-Month FI Ratio (Projected)
The projected FI ratio for the next 12 months, based on expected benchmark returns and current risk assets.

`fi_ratio_next_12m = (risk_assets * expected_annual_return) / projected_annual_expenses`

where:
- `expected_annual_return` is derived from historical benchmark returns or a target return assumption
- `projected_annual_expenses` is the trailing 12-month expenses or a user-defined budget