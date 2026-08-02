# 家計財務諸表 データスキーマ

## Asset input

`data/input/assets.csv` uses:

| Column | Meaning | Unit |
|---|---|---|
| `month` | Valuation month | `YYYY-MM` |
| `account_id` | Account master ID | ID |
| `asset_class` | Asset-class master ID | ID |
| `native_balance` | Balance in the row's native currency | native currency |
| `native_currency` | `JPY`, `USD`, or `EUR` | currency code |

`balance` remains accepted as a legacy alias for `native_balance`. A row may
omit `native_currency` only when the account master declares a single currency.
Rows belonging to `currency=multi` accounts must specify it.

## Calculated data

- `asset_valuations.csv`: native amount, currency, applied FX rate, and JPY value.
- `balance_sheet.csv`: JPY values expressed in 万円.
- `metrics.csv`: raw monthly returns and trailing metrics.
- `normalized.csv`: all `資産_*` and `分類_*` columns are JPY.
- `forecast.csv`: historical and forecast monthly data under the same units.
- `forecast_annual.csv`: annual flows, ending balances, and returns linked from
  raw monthly returns.
- `recalculation_diff.csv`: numeric before/after differences produced by
  `task audit:recalculate`.

## Measurement fields

| Field | Definition | Unit |
|---|---|---|
| `net_worth_contribution` | cash savings + pension/DC contribution | 万円 |
| `investment_gain_loss` | change in net worth less external contribution | 万円 |
| `return_base_assets` | previous month's risk + pension assets | 万円 |
| `raw_monthly_return` | gain/loss divided by return base | rate |
| `monthly_return` | trailing geometric mean of raw monthly returns | monthly rate |
| `raw_benchmark_return` | one-month JPY S&P 500 return | rate |
| `monthly_alpha` | portfolio return − benchmark return, when both defined | rate |

The authoritative contract is [ADR 0002](../adr/0002-financial-measurement-contract.md).
