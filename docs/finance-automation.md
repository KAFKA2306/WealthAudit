# Personal finance automation

Issue #28 の運用目標は、定例の手作業をなくし、本人認証が必要な時だけ人間へ返すことです。

## Runtime flow

```text
Windows Task Scheduler
  -> WSL2
  -> finance_sync_cli run
  -> retention-aware planner
  -> due source only
  -> local provider driver
  -> official export / app export
  -> data/incoming
  -> immutable raw archive + SHA256
  -> source state
  -> coverage audit

provider asks for MFA / passkey / OTP
  -> AUTH_REQUIRED for that source only
  -> other sources continue
```

daemon は使いません。PCが停止していた場合は Windows Task Scheduler の StartWhenAvailable で次回起動後に実行します。

## Install the scheduler

管理者権限が不要な範囲で Task Scheduler へ日次taskを登録します。PowerShellから:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_finance_scheduler.ps1 `
  -RepoPath /home/kafka/WealthAudit `
  -WslDistro Ubuntu-22.04 `
  -At 07:00
```

削除:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_finance_scheduler.ps1
```

実行ログは Git 管理外の:

```text
data/logs/finance-sync.log
```

へ保存します。

## Local driver configuration

driver設定は個人環境に依存するためGitへcommitしません。

既定:

```text
data/runtime/driver_commands.json
```

形式:

```json
{
  "schema_version": "wealthaudit.driver-commands.v1",
  "drivers": [
    {
      "source_id": "rakuten_card",
      "argv": [
        "python",
        "/absolute/local/path/provider_drivers/rakuten_card_export.py"
      ],
      "timeout_seconds": 600,
      "working_directory": null
    }
  ]
}
```

公開templateは `config/driver_commands.example.json` にあります。

### Security contract

- shell経由で実行しない
- password / OTP / token / cookie をargvへ入れない
- credentialをdriver JSONへ入れない
- browser storage stateは `.auth/` または `playwright/.auth/` 等のignored pathへ置く
- raw exportは `data/incoming/` 配下だけを受け付ける
- driverがそれ以外のファイルを返したら `EXPORT_OUTSIDE_INCOMING_ROOT` でfail-close
- provider 1つの失敗で他providerを止めない

## Provider driver stdout contract

provider driverはstdoutへJSONを1個だけ返します。

成功:

```json
{
  "status": "SUCCESS",
  "path": "/repo/data/incoming/rakuten_card/statement.csv",
  "original_filename": "利用明細.csv",
  "account_alias": "primary",
  "covered_from": "2026-09-01",
  "covered_to": "2026-09-30",
  "record_count": 42
}
```

本人認証が必要:

```json
{
  "status": "AUTH_REQUIRED",
  "error_code": "PASSKEY_REQUIRED"
}
```

失敗:

```json
{
  "status": "FAILED",
  "error_code": "SCHEMA_CHANGED"
}
```

MFA / CAPTCHA / passkeyを自動回避しません。認証が必要なら `AUTH_REQUIRED` とし、そのsourceだけ停止します。

## Commands

取得計画だけ確認:

```bash
task finance:plan
```

due providerを無人実行:

```bash
task finance:run
```

公式exportを手動で置いた場合のfallback:

```bash
uv run python -m src.infrastructure.finance_sync_cli ingest \
  rakuten_card data/incoming/rakuten_card/statement.csv \
  --covered-from 2026-09-01 \
  --covered-to 2026-09-30 \
  --record-count 42
```

## Human-work KPI

定例操作回数はKPIにしません。目標は:

```text
scheduled human work = 0
```

人間へ返してよいイベント:

- MFA
- OTP
- passkey
- CAPTCHA
- provider規約/同意画面の更新
- schema changeで安全に解釈できない場合
- coverage gap / reconciliation conflict

それ以外は自動処理します。

## Provider implementation order

履歴消失リスク順:

1. Mobile Suica
2. 城南信用金庫
3. 楽天キャッシュ
4. 楽天カード
5. Vpass
6. メルカード
7. PayPay
8. APLUS
9. long-history banks / securities

browser automationの目的はHTMLを正本化することではありません。公式サイト上の公式CSV/PDF export操作を自動化し、取得した公式artifactを正本のRaw Archiveへ渡すことです。


## Implemented provider driver: Zaim secondary probe

`scripts/provider_drivers/zaim_export.py` is the first concrete unattended provider driver.

Required local environment variables:

```text
ZAIM_CONSUMER_KEY
ZAIM_CONSUMER_SECRET
ZAIM_ACCESS_TOKEN
ZAIM_ACCESS_TOKEN_SECRET
```

Optional bounded query:

```text
ZAIM_START_DATE=YYYY-MM-DD
ZAIM_END_DATE=YYYY-MM-DD
```

It fetches `/v2/home/money` page-by-page, preserves the exact JSON responses in a ZIP under `data/incoming/zaim/`, records a manifest with SHA-256 per page, and hands that official/API artifact to the normal Raw Archive boundary.

This source remains `secondary_only=true`. WealthAudit does not assume that every bank/card item visible in the Zaim UI is exposed by the API. Completeness must be measured against primary official exports before any Zaim record is treated as coverage evidence.
