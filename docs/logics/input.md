# Input Data

This document describes the format of the input CSV files.

## Transaction Data (`data/input/`)

### `income.csv`
Contains income data.

- `month`: The month of the income (YYYY-MM).
- `account_id`: The ID of the account that received the income.
- `amount`: The amount of income in JPY.

### `expense.csv`
Contains expense data.

- `month`: The month of the expense (YYYY-MM).
- `method_id`: The ID of the payment method used for the expense.
- `amount`: The amount of the expense in JPY. Negative values are treated as adjustments or refunds.

### `assets.csv`
Contains asset balance data.

- `month`: The month of the asset balance snapshot (YYYY-MM).
- `account_id`: The ID of the account holding the asset.
- `asset_class`: The asset class of the asset.
- `balance`: The balance of the asset in its original currency.

### `market.csv`
Contains market data for currency exchange rates and stock indices.

- `month`: The month of the market data (YYYY-MM).
- `usd_jpy`: The USD/JPY exchange rate.
- `eur_jpy`: The EUR/JPY exchange rate.
- `sp500`: The S&P 500 index value.

## Master Data (`master/`)

### `accounts.csv`
Contains master data for accounts.

- `account_id`: The unique ID of the account.
- `name`: The name of the account.
- `type`: The type of the account (e.g., `bank`, `securities`).
- `currency`: The currency of the account (e.g., `JPY`, `USD`).
- `risk`: A flag indicating if the account holds risk assets (1 for true, 0 for false).

### `payment_methods.csv`
Contains master data for payment methods.

- `method_id`: The unique ID of the payment method.
- `name`: The name of the payment method.
- `settlement_account`: The ID of the account from which the payment is settled. Can be empty.

## Web Interface

A web form is available to simplify monthly data entry.

### Access
```bash
uv run python -m src.infrastructure.web
# Navigate to http://localhost:5000/input
```

### Features
- **Auto-fill**: Fixed items (Pension, DC) are pre-populated.
- **Defaults**: Variable items show last month's values.
- **Add/Remove**: Dynamically manage rows.
- **Save**: Appends to `data/input/*.csv`.

### Workflow
1. Open `/input` at month-end.
2. Update values and click **Save All Data**.
3. Run CLI to recalculate: `uv run python -m src.infrastructure.cli`
4. View dashboard at `/`.