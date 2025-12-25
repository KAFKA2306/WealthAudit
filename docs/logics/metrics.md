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