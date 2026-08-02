# 家計財務諸表 データスキーマ

## ディレクトリ構成

```text
.
├── data/
│   ├── input/
│   │   ├── income.csv
│   │   ├── expense.csv
│   │   ├── assets.csv
│   │   └── market.csv
│   └── calculated/
│       ├── cashflow.csv
│       ├── balance_sheet.csv
│       ├── metrics.csv
│       ├── normalized.csv
│       ├── forecast.csv
│       ├── forecast_annual.csv
│       └── forecast_parameters.csv
├── master/
│   ├── accounts.csv
│   ├── asset_classes.csv
│   ├── forecast_streams.csv
│   └── payment_methods.csv
```

## ID Sources

- `src/constants.py`
- `master/accounts.csv`
- `master/asset_classes.csv`
- `master/forecast_streams.csv`
- `master/payment_methods.csv`

## Data Models

```typescript
type Month = string; // YYYY-MM-DD (month-end)

interface Income {
  month: Month;
  account_id: AccountId;
  amount: number; // JPY
}

interface Expense {
  month: Month;
  method_id: PaymentMethodId;
  amount: number; // JPY
}

interface Asset {
  month: Month;
  account_id: AccountId;
  asset_class: AssetClassId;
  balance: number; // account currency units; consolidated JPY valuation for multi accounts
}

interface Market {
  month: Month;
  usd_jpy: number;
  eur_jpy: number;
  sp500: number;
}

interface Account {
  id: AccountId;
  name: string;
  type: AccountType;
  currency: Currency; // JPY, USD, EUR, or multi
  risk: number; // 0 or 1
}

interface PaymentMethod {
  id: PaymentMethodId;
  name: string;
  settlement_account?: AccountId;
}
```

## 計算ロジック依存関係

1. `data/input/*` → `data/calculated/cashflow.csv`, `data/calculated/balance_sheet.csv`
2. `data/calculated/*` → `data/calculated/metrics.csv`
3. `data/calculated/*` → `data/calculated/normalized.csv`
4. `normalized.csv` + `master/forecast_streams.csv` → `forecast.csv`
