# WealthAudit — 個人資産の計算・予測・警告を分離する財務監査基盤

[![Asset ledger contract](https://github.com/KAFKA2306/WealthAudit/actions/workflows/asset-ledger-contract.yml/badge.svg)](https://github.com/KAFKA2306/WealthAudit/actions/workflows/asset-ledger-contract.yml)
[![Validate monthly close state machine](https://github.com/KAFKA2306/WealthAudit/actions/workflows/monthly-close.yml/badge.svg)](https://github.com/KAFKA2306/WealthAudit/actions/workflows/monthly-close.yml)
[![Validate web security boundary](https://github.com/KAFKA2306/WealthAudit/actions/workflows/web-security.yml/badge.svg)](https://github.com/KAFKA2306/WealthAudit/actions/workflows/web-security.yml)

WealthAuditは、収入、支出、資産残高、市場データから、個人の貸借対照表、キャッシュフロー、資産配分、投資収益、FI指標、将来予測を再計算し、ローカルのWebダッシュボードで確認するための個人財務ワークスペースです。

単にグラフを表示するだけではなく、**実績と予測を分離し、入力不足、データの古さ、計算不能を警告として見せること**を重視します。

> **パッケージ名:** `bspl`  
> **Python:** 3.10以上  
> **主なUI:** Flask / Plotly / HTML  
> **利用形態:** ローカル実行  
> **公開上の注意:** 実際の家計・資産データはGitへ保存しません。

---

## 何ができるか

- 月次の収入、支出、資産残高、市場データを読み込む
- 貸借対照表と損益・キャッシュフロー相当の指標を再計算する
- 流動資産、リスク資産、年金資産、純資産合計を確認する
- 貯蓄率、リスク資産比率、投資収益率、ベンチマーク差を計算する
- 12か月、48か月、予測ベースのFI指標を確認する
- 30年間の資産推移をシナリオ計算する
- 実績期間と予測期間を明示的に分けて表示する
- グラフと同じ数値をアクセシブルな表でも確認する
- 最新実績月、更新時刻、欠損、重複、鮮度不足を警告する
- CSVとDrive同期用XLSXの間でimport、export、backup、restoreを行う
- 再計算前後の数値差分を監査する

予測は確定値ではありません。将来の収入、支出、運用収益、為替、市場価格などの前提に依存します。

---

## 実績と予測の境界

ダッシュボードは、現在月を自動的に実績へ含めません。原則として、**最後に完了した月までを実績**、それより後を予測として扱います。

```text
入力CSV
  → 月次計算
  → data/calculated/forecast.csv
  → 完了月まで: 実績
  → 完了月より後: 予測
  → 警告・要約・グラフ・同等データ表
```

予測を表示する画面では、背景付き領域と境界線で予測区間を示します。グラフだけでなく、同じデータを表でも確認できます。

次の場合は、正常値を装わず警告または「利用不可」と表示します。

- `forecast.csv`が存在しない
- 必須列が不足している
- 同一月が重複している
- 完了月までの実績が存在しない
- 最新行に欠損がある
- 最新実績月が期待する完了月より古い

---

## データの流れ

```text
ローカルの入力CSVまたはinput.xlsx
        │
        ▼
data/input/
        │
        ▼
ドメイン計算・正規化
        │
        ▼
data/calculated/
  forecast.csv
  forecast_annual.csv
  その他の計算結果
        │
        ├─ ローカルダッシュボード
        ├─ 正規化CSV export
        └─ view.xlsxへexport
```

`data/`、`input.xlsx`、`view.xlsx`、`backup/`は機微情報を含むため、`.gitignore`でGit管理外にしています。

---

## 必要な入力

実際の入力形式はコードと`docs/`を正準として確認してください。基本となるCSVは次のとおりです。

### `data/input/`

| ファイル | 内容 | 主な列 |
|---|---|---|
| `income.csv` | 月次収入 | `month`, `account_id`, `amount` |
| `expense.csv` | 月次支出 | `month`, `method_id`, `amount` |
| `assets.csv` | 月末資産残高 | `month`, `account_id`, `asset_class`, `balance` |
| `market.csv` | 為替・市場系列 | `month`, `usd_jpy`, `eur_jpy`, `sp500` |

### `master/`

| ファイル | 内容 |
|---|---|
| `accounts.csv` | 銀行、証券、財布などの口座定義 |
| `payment_methods.csv` | クレジットカード、口座振替などの支払方法 |
| `asset_classes.csv` | 現金、株式、年金などの資産クラス |

実データに列追加やschema変更がある場合は、READMEだけでなく計算コード、テスト、`docs/logics/`を確認してください。

---

## セットアップ

### 必要環境

- Python 3.10以上
- `uv`
- Git
- `go-task`は推奨

### 依存関係

```bash
uv sync --extra dev
```

通常利用だけで開発ツールが不要な場合:

```bash
uv sync
```

---

## 基本操作

利用可能なtaskを確認する:

```bash
task --list
```

### 月次計算

```bash
task run
```

`src.infrastructure.cli`を実行し、入力データから計算結果を生成します。

### 30年予測

```bash
task forecast
```

### ダッシュボード

```bash
task serve
```

起動後、標準設定では次を開きます。

```text
http://localhost:5000
```

実際のhostとportは起動ログと実装を優先してください。READMEにURLがあるだけでは、serverが起動済みであることを意味しません。

### 正規化データのexport

```bash
task export
```

### テスト

```bash
task test
```

### lint

```bash
task lint
```

### format

```bash
task format
```

---

## Drive / XLSX連携

ローカルのDrive同期領域にある`input.xlsx`と、Git管理外のCSVを同期できます。

### 準備状態を確認する

```bash
task drive:doctor
```

Driveがマウントされていない、対象ファイルがない、書込権限がない場合は、その状態を明示して停止します。

### XLSXからimport

```bash
task drive:import
```

### 計算結果をview.xlsxへexport

```bash
task drive:export
```

### backup

```bash
task drive:backup
```

### 明示的なbackupからrestore

```bash
task drive:restore -- <引数>
```

### 一連の同期

```bash
task sync-drive
```

このtaskは、import、計算、export、forecast、XLSX出力を順に行います。機微データとDrive環境がないCIでは、実データの再計算完了を主張できません。

---

## 再計算監査

```bash
task audit:recalculate
```

現在の入力から全出力を再計算し、変更前後の数値差分を出力します。

この監査には実際の非公開入力が必要です。公開リポジトリだけの状態で入力がない場合は、成功したように見せず、preflightで明示的に失敗します。

---

## ダッシュボードの構成

現在のダッシュボードは、次の意思決定を中心に構成されています。

- 現在の純資産はいくらか
- 直近月に純資産がどう変化したか
- キャッシュフローと投資損益を分離できているか
- 資産配分が意図したリスク水準か
- 貯蓄率やFI指標が改善しているか
- どこからが予測で、前提依存なのか
- 入力、鮮度、欠損に警告があるか

主な表示:

| 表示 | 内容 |
|---|---|
| 純資産 | 流動資産、リスク資産、年金資産、合計 |
| キャッシュフロー | 税引後収入、支出、投資損益、純資産増減 |
| 資産配分 | 資産クラス比率 |
| 財務比率 | 貯蓄率、リスク資産比率 |
| 投資収益 | portfolio return、benchmark return、alpha |
| FI | 12か月、48か月、予測FI比率 |
| 警告 | 欠損、重複、データ鮮度、計算不可 |

`1Y`、`All`、`+5Y`などの表示範囲を切り替えます。`+5Y`では実績と予測を同じものとして扱わず、境界を表示します。

---

## ディレクトリ構成

```text
src/
  domain/                  ドメインモデル
  use_cases/               計算、グラフ、要約などのロジック
  infrastructure/          CLI、Web、repository実装
scripts/
  forecast.py              長期予測
  export_normalized.py     正規化CSV export
  recalculate_audit.py     再計算差分監査
  sync_drive.py            XLSX import/export/doctor/backup/restore
templates/
  dashboard.html           ダッシュボード画面
tests/                     計算・UI・回帰テスト
docs/
  logics/                  計算仕様
  htmx/                    Web実装資料
  domain/                  ドメイン資料
master/                    口座・支払方法・資産クラスの定義
data/                      実入力と計算結果。Git管理外
Taskfile.yml               人間向けの主要操作入口
```

---

## 検証

### 通常のコード検証

```bash
task test
task lint
```

### UI変更の検証

ダッシュボードUIに関するworkflowでは、次を確認します。

- Pythonのcompile
- regression test
- 実績と予測の境界
- 警告表示
- グラフと同等のデータ表
- 画面上の主要な説明とアクセシビリティ契約

### 実データ検証

公開CIでできるテストと、非公開入力が必要な検証を分けます。

| 検証 | 公開CI | 非公開入力が必要 |
|---|---:|---:|
| unit test | 可 | 不要 |
| type / lint | 可 | 不要 |
| UI contract | 可 | 不要 |
| 実際の家計再計算 | 不可 | 必要 |
| Drive同期 | 不可 | 必要 |
| view.xlsxの内容確認 | 不可 | 必要 |

テスト成功だけで、利用者の最新資産データが正しく反映されたとは判断しません。

---

## 正準と生成物

| 対象 | 管理場所 |
|---|---|
| 計算ロジック | `src/domain/`, `src/use_cases/` |
| Web実装 | `src/infrastructure/web.py`, `templates/` |
| 長期予測 | `scripts/forecast.py` |
| Drive同期 | `scripts/sync_drive.py` |
| 口座・資産クラス定義 | `master/` |
| 実入力 | `data/input/`、Git管理外 |
| 計算結果 | `data/calculated/`、Git管理外 |
| XLSX運用ファイル | `input.xlsx`, `view.xlsx`、Git管理外 |
| backup | `backup/`、Git管理外 |

---

## セキュリティとプライバシー

このリポジトリは公開されていますが、利用データは公開対象ではありません。

コミットしないもの:

- 収入、支出、資産残高
- 口座番号や証券口座情報
- 個人名、住所、勤務先などの個人情報
- 実際の`input.xlsx`と`view.xlsx`
- Drive同期先の秘密パス
- backup
- APIキーや認証情報

PRやIssueへ実データのスクリーンショットを添付する場合も、金額、口座、個人情報の公開範囲を確認してください。

---

## 既知の制約

- 本リポジトリは家計データの自動取得サービスではありません。入力CSVまたはXLSXの準備が必要です。
- 30年予測はシナリオであり、将来収益やFI達成を保証しません。
- 市場データ、為替、benchmarkの更新頻度は入力に依存します。
- Drive同期はローカル環境とマウント状態に依存します。
- 公開CIでは非公開入力を用いた最終再計算を実行できません。
- ローカルダッシュボードのため、公開ホスティング済みサービスとしては扱いません。
- `bspl`という内部package名は残っています。リポジトリ名との統一は別の移行作業です。

---

## README.mdと開発文書

READMEは、人間が目的、入力、計算、操作、検証、プライバシー、制約を理解する正準入口です。

詳細な計算式や実装判断は次を参照してください。

- [`docs/logics/`](docs/logics/) — 計算ロジック
- [`docs/htmx/`](docs/htmx/) — ダッシュボード実装
- [`docs/domain/`](docs/domain/) — ドメインモデル
- [`Taskfile.yml`](Taskfile.yml) — 主要コマンド

---

## ライセンス

MIT License。詳細は[`LICENSE`](LICENSE)を参照してください。

**README実体監査:** 2026年8月4日