# Forecast Logic

## Inputs

- `data/calculated/normalized.csv`
- `master/accounts.csv`
- `master/forecast_streams.csv`
- `src/constants.py`

Concrete output columns remain: `収入_*`, `支出_*`, `資産_*`, `分類_*`.

Forecast classification comes from `master/forecast_streams.csv`: `cash_income`, `asset_contribution`, `drawdown`, `transfer_like`, `other`.

## Formulas

```text
cash_income(t) =
  sum(stream_amount(t) where kind = cash_income)

asset_contribution(t) =
  sum(stream_amount(t) where kind = asset_contribution)

expenditure(t) =
  sum(支出_*)

cash_savings(t) =
  cash_income(t) - expenditure(t)

net_worth_contribution(t) =
  cash_savings(t) + asset_contribution(t)
```

```text
after_tax_income = cash_income
net_savings = cash_savings

liquid_assets =
  分類_現金・預金 / 10000

risk_assets =
  risk asset classes / 10000

pension_assets =
  分類_年金 / 10000

total_financial_assets =
  liquid_assets + risk_assets + pension_assets

investment_gain_loss(t) =
  total_financial_assets(t)
  - total_financial_assets(t-1)
  - net_worth_contribution(t)
```

## Outputs

- Forecast starts after the latest month in `normalized.csv`.
- Forecast horizon is 360 months.
- Metrics are recalculated after historical and forecast rows are combined.

| Value | Meaning |
|-------|---------|
| `60` | +5 years |
| `120` | +10 years |
| `360` | +30 years |

See [htmx/graph.md](../htmx/graph.md#6-forecast-toggle-feature).
