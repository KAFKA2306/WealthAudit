# Forecast Logic

## Inputs and units

- `data/calculated/normalized.csv`
- `master/accounts.csv`
- `master/asset_classes.csv`
- `src/constants.py`

`収入_*`, `支出_*`, `資産_*`, and `分類_*` are JPY. Balance-sheet and cash-flow
summary columns are 万円. Ratio columns are decimal rates.

## Cash flow

```text
cash_savings = cash_income - expenditure
net_worth_contribution = cash_savings + asset_contribution
```

## Assets and returns

The forecast compounds risk and pension assets with the portfolio scenario,
then applies external contributions. Liquid assets have no assumed investment
return.

```text
monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
```

Historical portfolio assumptions are estimated from `raw_monthly_return`, never
from the already-smoothed `monthly_return` field. Annual return is:

```text
annual_return(year) = product(1 + raw_monthly_return in year) - 1
```

Portfolio and benchmark assumptions are independent. If
`BENCHMARK_EXPECTED_ANNUAL_RETURN` is `None`, forecast benchmark and alpha are
left undefined.

## Income and expense boundaries

- Salary growth is applied only after an April raise boundary occurring after
  the final actual month. The first forecast month does not receive an automatic
  one-year raise.
- Variable-expense annual trend is compounded once per forecast year instead of
  being applied only once for the entire 30-year horizon.

## Outputs

- Forecast starts one calendar month after the latest normalized row.
- Horizon: 360 months.
- `forecast.csv` keeps raw and trailing return fields.
- `forecast_annual.csv` links raw monthly returns.
- `task audit:recalculate` writes `recalculation_diff.csv`.

See [ADR 0002](../adr/0002-financial-measurement-contract.md).
