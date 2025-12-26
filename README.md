# 💰 WealthAudit

**家計簿から資産形成を可視化する個人財務ダッシュボード**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![HTMX](https://img.shields.io/badge/HTMX-2.0-purple.svg)](https://htmx.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ 特徴

| 機能 | 説明 |
|------|------|
| 📊 **自動BS/PL計算** | CSV入力から貸借対照表・損益計算書を自動生成 |
| 📈 **30年予測** | 過去データから将来の資産推移をシミュレーション |
| 🎯 **FIRE進捗** | 経済的自立（FI）達成度をリアルタイム表示 |
| 💹 **投資分析** | ベンチマーク（S&P 500）対比のα（超過リターン）を計算 |
| 🌐 **Webダッシュボード** | HTMXによるインタラクティブな可視化 |

---

## 🚀 クイックスタート

```bash
# 1. リポジトリをクローン
git clone <repository-url>
cd bspl

# 2. 依存関係をインストール
uv sync

# 3. 計算を実行
task run

# 4. ダッシュボードを起動
task serve
```

🌐 ブラウザで http://localhost:5000 を開く

---

## 📂 データ準備

本システムを使用するには、以下のCSVファイルを準備する必要があります。

### 1. トランザクション・資産データ (`data/input/`)

| ファイル | 説明 | 必須カラム |
|----------|------|------------|
| `income.csv` | 月次収入履歴 | `month`, `account_id`, `amount` |
| `expense.csv` | 月次支出履歴 | `month`, `method_id`, `amount` |
| `assets.csv` | 月末資産残高 | `month`, `account_id`, `asset_class`, `balance` |
| `market.csv` | 市場データ (S&P500, FX) | `month`, `usd_jpy`, `eur_jpy`, `sp500` |

### 2. マスタデータ (`master/`)

| ファイル | 説明 |
|----------|------|
| `accounts.csv` | 口座定義（銀行、証券、財布など） |
| `payment_methods.csv` | 支払方法定義（クレカ、口座振替など） |
| `asset_classes.csv` | 資産クラス定義（現金、株式、年金など） |

---

## 📁 プロジェクト構成

```
bspl/
├── data/
│   ├── input/          # 入力データ（収入・支出・資産）
│   └── calculated/     # 計算結果
│       ├── forecast.csv        # 30年予測（メインデータ）
│       └── forecast_annual.csv # 年次サマリー
├── master/             # マスタデータ（口座・支払方法）
├── src/
│   ├── domain/         # ドメインモデル
│   ├── use_cases/      # ビジネスロジック
│   └── infrastructure/ # CLI・Web・リポジトリ
├── templates/          # HTMLテンプレート
└── docs/               # 詳細ドキュメント
```

---

## 📊 ダッシュボード

6つのグラフで財務状況を可視化:

| グラフ | 内容 |
|--------|------|
| **Net Worth Trend** | 資産推移（流動・リスク・年金） |
| **Cash Flow** | 収入・支出・投資損益・Total Flow |
| **Asset Allocation** | 資産配分比率の推移 |
| **Financial Ratios** | 貯蓄率・リスク資産比率 |
| **Investment Returns** | 月次リターン・ベンチマーク比較 |
| **FI Ratios** | FIRE達成度（12m/48m/Proj） |

### 📅 表示切替

| ボタン | 表示範囲 |
|--------|----------|
| **1Y** | 過去1年間 |
| **All** | 全履歴（実績データ） |
| **+5Y** | 過去1年 + 将来5年予測 |

---

## 🛠️ コマンド

```bash
task run       # BS/PL計算を実行
task forecast  # 30年予測を生成
task serve     # Webダッシュボードを起動
task export    # 正規化データをエクスポート
task test      # テストを実行
task lint      # コードチェック
task format    # コード整形
```

---

## 📖 ドキュメント

| ドキュメント | 内容 |
|--------------|------|
| [docs/logics/](docs/logics/) | 計算ロジックの詳細仕様 |
| [docs/htmx/](docs/htmx/) | ダッシュボード実装ガイド |
| [docs/domain/](docs/domain/) | ドメインモデル定義 |

---

## 📝 必要環境

- **Python** >= 3.10
- **[uv](https://github.com/astral-sh/uv)** - 高速パッケージマネージャー
- **[go-task](https://taskfile.dev/)** - タスクランナー（オプション）

---

## 📜 ライセンス

MIT License
