# Normalized Output

正規形テーブルの出力ドキュメント。

## 概要

`task export` コマンドで、すべての入力データと計算データを1つのCSVファイルに統合して出力します。

## 出力ファイル

`data/calculated/normalized.csv`

## カラム順序（財務ロジック）

### 1. 主キー
- `month`: 年月 (YYYY-MM)

### 2. P/L（損益）
#### 収入
- `収入_*`: 口座別収入（`master/accounts.csv` の `name` を使用）

#### 支出
- `支出_*`: 支払方法別支出（`master/payment_methods.csv` の `name` を使用）

#### キャッシュフロー
- `after_tax_income`: 税引後収入
- `expenditure`: 支出合計
- `net_savings`: 純貯蓄

### 3. B/S（貸借対照表）
#### 口座別 (`資産_*`)
- `資産_*`: 口座別残高（`master/accounts.csv` の `name` を使用）

#### 資産分類別 (`分類_*`)
- `分類_*`: 資産クラス別残高（`master/asset_classes.csv` の `name` を使用）

#### 集計値
- `liquid_assets`: 流動資産
- `risk_assets`: リスク資産
- `pension_assets`: 年金資産
- `total_financial_assets`: 金融資産合計
- `investment_gain_loss`: 投資損益

### 4. 財務指標
- `savings_rate`: 貯蓄率
- `risk_asset_ratio`: リスク資産比率
- `monthly_return`: 月次リターン
- `monthly_alpha`: 月次アルファ
- `benchmark_return`: ベンチマークリターン
- `fi_ratio_12m`: FI比率（12ヶ月）
- `fi_ratio_48m`: FI比率（48ヶ月）
- `fi_ratio_next_12m`: FI比率（次12ヶ月）

## 実行方法

```bash
task export
# または
uv run python scripts/export_normalized.py
```
