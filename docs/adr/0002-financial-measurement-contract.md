# ADR 0002: Financial measurement contract

- Status: Accepted
- Date: 2026-08-03
- Supersedes: ambiguous unit and return definitions in the forecast documentation

## Context

The previous pipeline stored native-currency asset balances in `資産_*` and
`分類_*`, while the balance sheet converted foreign currencies to JPY. It then
calculated a total-portfolio gain against a risk-assets-only denominator. The
forecast compounded a rolling return as though it were a raw observation and
used the same assumption for both portfolio and benchmark.

## Decision

1. `assets.csv` stores a native amount (`native_balance`; legacy `balance` is
   accepted) and may store `native_currency` per row.
2. A single-currency account may omit row currency. An account declared as
   `multi` must specify `native_currency` on every asset row.
3. Valuation uses the latest market observation at or before the asset month.
   A future observation is never used.
4. `asset_valuations.csv` preserves native amount, currency, FX rate, and JPY
   value. Every `資産_*` and `分類_*` column in normalized and forecast output is
   JPY.
5. Balance-sheet output remains in 万円. The investment scope is risk assets plus
   pension assets.
6. For consecutive calendar months:

   ```text
   investment_gain_loss(t)
     = total_financial_assets(t)
     - total_financial_assets(t-1)
     - net_worth_contribution(t)

   return_base_assets(t)
     = risk_assets(t-1) + pension_assets(t-1)

   raw_monthly_return(t)
     = investment_gain_loss(t) / return_base_assets(t)
   ```

   A gap in months produces no monthly return.
7. `monthly_return` is the trailing geometric mean of raw monthly returns.
   Calendar-year return links only the raw monthly returns inside that year.
8. Effective annual rates are converted with `(1 + annual_rate) ** (1/12) - 1`.
9. Portfolio and benchmark forecast assumptions are separate. When no benchmark
   assumption is configured, forecast benchmark return and alpha are undefined.
10. Total Wealth Flow is `net_worth_contribution + investment_gain_loss`.

## Consequences

- Existing historical outputs must be recalculated.
- Native and JPY values remain auditable without mixing units.
- Multi-currency accounts require more explicit input but cannot be silently
  misvalued.
- Forecast alpha is absent rather than mechanically zero when no benchmark
  scenario exists.
