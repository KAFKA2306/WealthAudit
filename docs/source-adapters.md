# Source Adapter contract

WealthAudit の取得境界は次に固定します。

```text
authenticate -> fetch raw -> parse -> normalize -> validate -> handoff
```

provider 固有の認証・field mapping・pagination は adapter / API client に閉じ込め、BS/PL/CF・FI・forecast の計算は既存 domain / use-case 層だけで行います。

## Canonical handoff

正規化後に月次 pipeline へ渡せる table は既存の4種だけです。

- `income`
- `expense`
- `assets`
- `market`

共有 validator は unknown table、必須列欠損、対象月不一致、重複 identity、未知 account / payment method を fail-close します。失敗した取得は成功した `AdapterResult` を生成せず、確定済み月を更新しません。

## Personal finance acquisition control plane

Issue #28 の個人金融取得は、provider parser より手前に retention-aware acquisition control plane を置きます。

```text
source policy
  -> due / noop / wait-for-auth / review
  -> official export or device history
  -> immutable raw archive + SHA256
  -> provider SourceAdapter
  -> canonical tables
  -> coverage audit
```

`config/finance_sources.json` は公開可能な provider policy catalog です。実口座番号、カード番号、credential、cookie、token、個人aliasは置きません。

各 source は少なくとも次を持ちます。

- `source_id`
- `priority`
- `acquisition_method`
- `cadence_days`
- `retention_days`
- `safety_margin_days`
- `official_reference`
- `max_records`
- `secondary_only`

取得間隔は固定月次ではなく、

```text
min(cadence_days, retention_days - safety_margin_days)
```

で決めます。履歴保持期限が不明または実質無期限の provider は `retention_days=null` とし、cadence のみで再取得します。

### Runtime state

state は Git 管理外の `data/state/sources/<source_id>.json` に保存します。

status:

- `NEVER_RUN`
- `OK`
- `AUTH_REQUIRED`
- `FAILED`
- `SCHEMA_CHANGED`
- `GAP_DETECTED`

`AUTH_REQUIRED` は provider 単位の停止です。他 source は継続します。MFA / OTP / passkey / CAPTCHA を回避せず、人間へ認証境界だけ渡します。

### Raw archive

公式 export / app export / device history の取得結果は、加工前bytesを

```text
data/raw/<source>/<account_alias>/<yyyy-mm-dd>/<sha-prefix>_<filename>
```

へ保存し、SHA-256を provenance とします。

同じbytesの再投入は同じartifactへ収束し、raw file countを増やしません。

Gitへ保存しないもの:

- raw financial payload
- cookie / browser storage state
- token / API secret
- password / OTP / passkey secret
- HAR / HTML dump containing sessions

### CLI

```bash
task finance:plan
```

全sourceについて `ACQUIRE / NOOP / WAIT_FOR_AUTH / REVIEW_REQUIRED` をJSONで出力します。

公式ファイルを取得したdriverは次の境界へ渡します。

```bash
uv run python -m src.infrastructure.finance_sync_cli \
  ingest <source_id> <official-export-path> \
  --account-alias <local-alias> \
  --covered-from YYYY-MM-DD \
  --covered-to YYYY-MM-DD \
  --record-count N
```

認証が必要なら、そのproviderだけを止めます。

```bash
uv run python -m src.infrastructure.finance_sync_cli \
  auth-required <source_id>
```

## Implemented official API clients

`src/interface_adapters/official_apis.py` は、外部一次データを取得する薄い HTTPS client を提供します。

| source | purpose | auth | official boundary |
|---|---|---|---|
| BOJ Time-Series Data Search API | FX / 金利 / macro 等の公式時系列 | 不要 | `www.stat-search.boj.or.jp` |
| ECB Data Portal API | FX / macro / SDMX data | 不要 | `data-api.ecb.europa.eu` |
| e-Stat API v3.0 | CPI / 家計 / 労働等の政府統計 | `ESTAT_APP_ID` | `api.e-stat.go.jp` |
| J-Quants API V2 | 日本株価格・企業データ | `JQUANTS_API_KEY` | `api.jquants.com` |

clients は provider payload を取得するだけで canonical table を勝手に推測しません。どの series / field を `market` や `assets` へ採用するかは、単位・頻度・時点・通貨・調整方法を明示した provider-specific normalizer で別途固定します。

## MCP usage

WealthAudit MCP から、上記 API の bounded read と source capability の照会が可能です。secret は configured boolean としてのみ露出し、credential 値は返しません。

J-Quants の公式 `J-Quants/j-quants-doc-mcp` は API endpoint 検索・詳細・サンプルコード・FAQ 用です。実データは J-Quants API V2 から取得するため、この2つを混同しません。

## Safety / provenance

- HTTPS 以外、または allow-list 外 host を拒否
- external response は 5 MB 上限
- e-Stat `appId` は provenance URL で redaction
- J-Quants API key は `x-api-key` header のみ
- raw SHA-256 と retrieval timestamp を保持
- raw download、HTML dump、cookies、tokens、credentials を Git に保存しない

## Official references

- BOJ: https://www.boj.or.jp/en/statistics/outline/notice_2026/not260218a.htm
- ECB: https://data.ecb.europa.eu/help/api/overview
- e-Stat: https://www.e-stat.go.jp/api/api-info/api-spec
- J-Quants V2 / official MCP: https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260119.html
- J-Quants official Python client: https://github.com/J-Quants/jquants-api-client-python
- J-Quants documentation MCP: https://github.com/J-Quants/j-quants-doc-mcp
