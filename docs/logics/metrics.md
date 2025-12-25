# Financial Metrics Logic

This document describes the logic for calculating financial metrics. The calculations are performed by the `MetricsCalculator`.

## Savings Rate
The savings rate is the ratio of net savings to after-tax income, calculated over the **trailing 12 months** to smooth out seasonality.

`savings_rate = sum(net_savings, 12m) / sum(after_tax_income, 12m)`

## Risk Asset Ratio
The risk asset ratio is the ratio of risk assets (including pension assets) to total financial assets.

`risk_asset_ratio = (risk_assets + pension_assets) / total_financial_assets`

## Monthly Return (ROI) - Geometric Mean
The monthly return describes the investment performance. To reduce short-term volatility and strictly measure performance trends, we calculate the **Geometric Mean** of the monthly returns over the **trailing 12 months**.

1. **Raw Monthly Return**: `raw_return = investment_gain_loss / prev_month_risk_assets`
2. **Geometric Mean (12m)**: `monthly_return = (product(1 + raw_return, 12m))^(1/12) - 1`

## Monthly Alpha
The monthly alpha is the excess return of the investment compared to the benchmark (S&P 500 JPY), also calculated using the Geometric Mean over the same 12-month period.

`monthly_alpha = monthly_return - benchmark_return`

## Benchmark Return
The benchmark return is the **Geometric Mean** of the S&P 500 (JPY) monthly returns over the **trailing 12 months**.

1. **Raw Benchmark Return**: `raw_benchmark = (sp500_jpy_current - sp500_jpy_prev) / sp500_jpy_prev`
2. **Geometric Mean (12m)**: `benchmark_return = (product(1 + raw_benchmark, 12m))^(1/12) - 1`

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
- `expected_annual_return` is currently set to **5.0%** (0.05).
- `projected_annual_expenses` is the trailing 12-month expenses or a user-defined budget