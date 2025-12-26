# 家計財務諸表 データスキーマ

## 概要
正規化されたデータ構造の定義。

---

## ディレクトリ構成

```
.
├── data/
│   ├── input/           # 手入力データ（ユーザー責任）
│   │   ├── income.csv
│   │   ├── expense.csv
│   │   ├── assets.csv
│   │   └── market.csv
│   └── calculated/      # 自動計算（システム責任）
│       ├── cashflow.csv
│       ├── balance_sheet.csv
│       ├── metrics.csv
│       ├── normalized.csv
│       ├── forecast.csv
│       ├── forecast_annual.csv
│       └── forecast_parameters.csv
├── master/              # マスタデータ
│   ├── accounts.csv
│   ├── asset_classes.csv
│   └── payment_methods.csv
```

---

## 型定義 (TypeScript Like)

```typescript
// Enums from src/constants.py

enum AccountId {
    YUCHO = 'yucho',
    SONY = 'sony',
    DEUTSCHE = 'deutsche',
    MINNA = 'minna',
    JONAN = 'jonan',
    WISE = 'wise',
    SBI_SEC = 'sbi_sec',
    RAKUTEN_SEC = 'rakuten_sec',
    MONEX_SEC = 'monex_sec',
    BINANCE = 'binance',
    KOSEI_NENKIN = 'kosei_nenkin',
    DC = 'dc',
}

enum AssetClassId {
    CASH = 'cash',
    STOCK_JP = 'stock_jp',
    STOCK_US = 'stock_us',
    FUND = 'fund',
    FX = 'fx',
    CRYPTO = 'crypto',
    PENSION = 'pension',
    VC = 'vc',
}

enum PaymentMethodId {
    SMBC_1 = 'smbc_1',
    SMBC_2 = 'smbc_2',
    RAKUTEN_1 = 'rakuten_1',
    RAKUTEN_2 = 'rakuten_2',
    EPOS = 'epos',
    MONEX_CARD = 'monex_card',
    SONY_CARD = 'sony_card',
    WISE = 'wise',
    CASH = 'cash',
    ADJUSTMENT = 'adjustment',
}

enum AccountType {
    BANK = 'bank',
    SECURITIES = 'securities',
    CRYPTO = 'crypto',
    PENSION = 'pension',
}

enum Currency {
    JPY = 'JPY',
    USD = 'USD',
    EUR = 'EUR',
    MULTI = 'multi',
}

// Data Models from src/domain/entities/models.py

type Month = string; // YYYY-MM

interface Income {
  month: Month;
  account_id: AccountId;
  amount: number; // JPY
}

interface Expense {
  month: Month;
  method_id: PaymentMethodId;
  amount: number; // JPY (Negative for adjustments)
}

interface Asset {
  month: Month;
  account_id: AccountId;
  asset_class: AssetClassId;
  balance: number; // Original Currency
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
  currency: Currency;
  risk: number; // 0 or 1
}

interface PaymentMethod {
  id: PaymentMethodId;
  name: string;
  settlement_account?: AccountId; // Link to Account
}
```

---

## 計算ロジック依存関係

1. **基礎集計** (`data/input/*` → `calculated/cashflow`, `calculated/balance_sheet`)
   - 収入: `input/income.csv` を月次・口座別に集計
   - 支出: `input/expense.csv` を月次・集計
   - 資産: `input/assets.csv` × `input/market.csv` (為替) で円換算

2. **指標計算** (`calculated/*` → `calculated/metrics`)
   - 貯蓄率、リスク性資産比率などのKPI導出

---

## 注意事項

- **調整項目 (`adjustment`)**: 支出のマイナスとして計上し、純粋な支出額を補正するために使用する。
- **引落口座**: クレジットカードの支払いは `master/payment_methods.csv` の `settlement_account` で定義された口座から資金移動が発生するものとみなす（CF上の支出はカード利用月基準）。
