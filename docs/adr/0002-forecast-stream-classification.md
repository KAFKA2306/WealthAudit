# ADR 0002: Concrete Input Columns with Forecast Stream Classification

Date: 2026-07-09
Decision Status: Accepted

## Context

WealthAudit uses concrete account and asset names in user-facing data:

- `income.csv` records observed monthly inflows by `account_id`
- `assets.csv` records month-end balances by `account_id` and `asset_class`
- `normalized.csv` expands those records into concrete columns such as `収入_楽天銀行`, `収入_ソニー銀行`, `資産_みんなの銀行`, and `資産_確定拠出年金`

The concrete column names are required. They make manual review, spreadsheet input, and financial inspection practical.

However, forecast logic currently infers behavior from concrete Japanese column names. This breaks when the economic stream stays the same but the account changes. Example:

```text
main salary deposit destination changed from Sony Bank to Rakuten Bank
```

The real-world stream is continuous, but account-based forecasting sees one income series disappearing and another appearing.

The same problem applies more broadly:

- `みんなの銀行` may represent a temporary drawdown or special inflow pattern
- `WISE` may represent transfer-like or foreign-currency-adjacent behavior
- `厚生年金` and `確定拠出年金` are asset contribution inflows, not bank cash salary
- securities, crypto, pension, and cash accounts need different forecast policies

## Decision

Keep concrete input and output columns. Add internal forecast classification metadata.

User-facing files must continue to expose concrete names:

```text
収入_楽天銀行
収入_ソニー銀行
収入_みんなの銀行
収入_厚生年金
収入_確定拠出年金
資産_楽天銀行
資産_ソニー銀行
資産_みんなの銀行
資産_厚生年金
資産_確定拠出年金
```

Forecast logic must not infer business meaning by grepping display names.

Instead, forecast behavior must be driven by master metadata, such as:

```csv
stream_id,display_name,kind,source_account_ids,forecast_to_account_id
main_salary,主給与,cash_income,sony;rakuten,rakuten
minna_drawdown,みんなの銀行,drawdown,minna,minna
wise_transfer,WISE,transfer_like,wise,wise
kosei_nenkin_contrib,厚生年金積立,asset_contribution,kosei_nenkin,kosei_nenkin
dc_contrib,確定拠出年金積立,asset_contribution,dc,dc
```

The exact file name and columns may change during implementation, but the architectural rule is fixed:

```text
Concrete columns for humans.
Classified streams and policies for forecasts.
```

## Forecast Semantics

Income-like observed inflows should be classified into at least these kinds:

- `cash_income`: bank-visible net cash income, including salary and bonus deposits
- `asset_contribution`: non-bank or restricted-account contribution that increases net worth
- `drawdown`: temporary inflow or account rundown behavior
- `transfer_like`: operational transfer or foreign-currency-adjacent flow that should not be treated as durable salary by default
- `other`: fallback behavior with conservative averaging

Asset accounts should also have policy classification:

- `cash_buffer`: bank, cash, and operational liquidity accounts
- `investment`: securities accounts
- `crypto`: crypto account
- `pension`: pension and DC accounts
- `transfer`: transfer or multi-currency operational accounts

## Forecast Accounting Logic

Forecasting must separate cash-flow accounting from net-worth accounting.

`cash_income` is bank-visible income that can fund expenses. `asset_contribution` is not spendable cash, but it is still an external inflow that increases net worth. Therefore pension and DC contribution streams must not be discarded; they must be excluded from cash savings and included in net-worth contribution.

The required formulas are:

```text
cash_income(t) =
  sum(stream_amount(t) where kind = cash_income)

asset_contribution(t) =
  sum(stream_amount(t) where kind = asset_contribution)

expense(t) =
  sum(observed or forecast expense streams)

cash_savings(t) =
  cash_income(t) - expense(t)

net_worth_contribution(t) =
  cash_savings(t) + asset_contribution(t)

investment_gain_loss(t) =
  total_financial_assets(t)
  - total_financial_assets(t-1)
  - net_worth_contribution(t)
```

This replaces the weaker formula:

```text
investment_gain_loss(t) =
  total_financial_assets(t)
  - total_financial_assets(t-1)
  - net_savings(t)
```

because `net_savings` alone does not explain non-cash pension/DC contributions.

Concrete forecast output still writes to concrete columns:

```text
main_salary stream forecast -> 収入_楽天銀行
kosei_nenkin_contrib stream forecast -> 収入_厚生年金
dc_contrib stream forecast -> 収入_確定拠出年金
```

For account destination changes, the stream is forecast once and assigned to the current destination:

```text
main_salary history = 収入_ソニー銀行 + 収入_楽天銀行
future main_salary -> 収入_楽天銀行
future 収入_ソニー銀行 -> 0 unless another stream maps to sony
```

For assets, forecast logic should apply policy by account classification:

```text
cash_buffer(t) =
  prior cash_buffer + cash_savings allocation

investment(t) =
  prior investment * (1 + investment_return_policy) + investment allocation

pension(t) =
  prior pension * (1 + pension_return_policy) + asset_contribution allocation

crypto_or_vc(t) =
  prior balance * account-specific return policy
```

The implementation may keep the existing concrete `after_tax_income`, `net_savings`, and `investment_gain_loss` column names for compatibility, but their definitions must be documented:

- `after_tax_income`: bank-visible cash income, not gross salary
- `net_savings`: cash savings after observed expenses
- `asset_contribution`: separate derived value or forecast parameter, even if not exposed as a primary dashboard column
- `investment_gain_loss`: residual after both cash savings and asset contributions

## Rationale

Concrete columns are necessary because this is a personal finance audit tool, not a generic ledger product. The user needs recognizable account names in CSV, spreadsheet, and dashboard outputs.

At the same time, forecast behavior must model economic continuity, not account-name continuity. A salary stream can move from one bank to another without becoming a new income source. Pension and DC contributions can increase net worth without being spendable cash income.

This separation keeps input simple while making forecasts more robust.

## Consequences

Positive:

- salary destination changes no longer corrupt long-range forecasts
- user-facing CSV and spreadsheet columns remain concrete
- `みんなの銀行`, `WISE`, pension, DC, securities, crypto, and ordinary bank accounts can each receive distinct policies
- forecast logic becomes auditable through master CSVs instead of hidden string matching

Negative:

- one new master classification layer is required
- forecast implementation must maintain mapping from concrete columns to internal streams
- incorrect master metadata can still produce incorrect forecasts

## Implementation Notes

Replace display-name checks in `scripts/forecast.py` with metadata-driven classification.

Do not solve account changes by adding more string checks such as `楽天` to existing conditions.

The first implementation should:

- add a forecast stream master CSV
- map `sony` and `rakuten` into one salary stream with `forecast_to_account_id = rakuten`
- classify `minna`, `wise`, `kosei_nenkin`, and `dc` explicitly
- calculate `cash_savings`, `asset_contribution`, and `net_worth_contribution` separately
- keep `normalized.csv` concrete column names unchanged
- export forecast values back into concrete `収入_*` and `資産_*` columns

## Non-Goals

This ADR does not require:

- anonymizing accounts
- adding gross salary, tax, or insurance detail inputs
- replacing concrete spreadsheet columns with abstract stream names
- introducing Google Sheets API or OAuth
