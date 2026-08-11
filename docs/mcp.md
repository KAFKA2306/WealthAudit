# WealthAudit local MCP + official external APIs

WealthAudit の MCP は `127.0.0.1` に固定した read-only gateway です。家計・資産の raw input を公開せず、既存の計算結果と、allow-list 済みの公式外部 API だけを読み出します。外部 API は **データ取得源**であり、BS/PL/CF や FI 指標の計算エンジンではありません。

## Protocol / SDK

新規MCP実装は正式MCP `2026-07-28` とMCP Python SDK v2を基準にします。SDK v2の高水準server classである `MCPServer` を使い、2026-07-28側では旧 `initialize` / `initialized` handshakeや `Mcp-Session-Id` を新規依存にしません。

- MCP specification release: https://modelcontextprotocol.io/specification/2026-07-28
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- SDK v2 changes: https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md

## Privacy boundary

- bind 先は `127.0.0.1` 固定
- `data/`, `input.xlsx`, `view.xlsx`, `backup/` は Git 管理外
- raw input workbook/CSV を MCP response に返さない
- 絶対ローカルパスを返さない
- write / mutation tool を提供しない
- `ESTAT_APP_ID` と `JQUANTS_API_KEY` の値を response / provenance / URL に返さない
- 外部 API は HTTPS + provider host allow-list を強制する
- 外部 API response は 5 MB を上限として fail-close する

## Start

```bash
python -m pip install -e '.[mcp]'
python -m src.interface_adapters.mcp_server
```

Streamable HTTP endpoint は loopback の `127.0.0.1:8012` です。

## Local financial tools

- `get_financial_snapshot`
- `get_balance_sheet`
- `get_cash_flow`
- `get_asset_allocation`
- `get_investment_returns`
- `get_fi_metrics`
- `get_forecast`
- `get_warnings`
- `get_data_freshness`
- `get_audit_diff`

これらは既存の `FinancialReadModel` / domain calculation を共有し、MCP 側で財務計算を再実装しません。`forecast.csv:is_forecast` を actual / forecast 境界の正本とし、欠損を 0 に変換しません。

## External API / MCP tools

- `get_external_data_sources`: provider、transport、capability、credential の configured boolean を返す。secret 値は返さない。
- `get_boj_time_series`: 日本銀行「時系列統計データ検索サイト」コード API (`/api/v1/getDataCode`) を読み出す。
- `get_ecb_series`: ECB Data Portal の SDMX REST data endpoint を読み出す。
- `get_estat_stats_data`: e-Stat API v3.0 `getStatsData` を `ESTAT_APP_ID` で読み出す。response の request URL では app ID を `REDACTED` に置換する。
- `get_jquants_daily_bars`: J-Quants API V2 `/equities/bars/daily` を `JQUANTS_API_KEY` header で読み出す。API key は URL / response に含めない。

J-Quants が公開している `J-Quants/j-quants-doc-mcp` は API 仕様検索・endpoint 詳細・サンプルコード・FAQ 用の公式 documentation MCP として registry に載せます。これは市場データ取得 API の代替ではありません。

## Source of truth / official references

- BOJ API launch: https://www.boj.or.jp/en/statistics/outline/notice_2026/not260218a.htm
- BOJ API guide: https://www.stat-search.boj.or.jp/ssi/docs/info/nme_aphelp_en.html
- ECB Data Portal API: https://data.ecb.europa.eu/help/api/overview
- e-Stat API v3.0: https://www.e-stat.go.jp/api/api-info/api-spec
- J-Quants API V2 / official MCP announcement: https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260119.html
- J-Quants official Python V2 client: https://github.com/J-Quants/jquants-api-client-python
- J-Quants official documentation MCP: https://github.com/J-Quants/j-quants-doc-mcp

## Provenance contract

利用可能なlocal financial rowは、値だけでなく次のmachine-readable envelopeを返します。

- `canonical_id`: `wealthaudit:actual:<YYYY-MM>` または `wealthaudit:forecast:<YYYY-MM>`
- `schema_version`
- `period`
- `actual_or_forecast`
- `data_as_of`
- `generated_at`
- `input_source`: repository-relative pathのみ
- `input_hash`: SHA-256
- `freshness`
- `stale`
- `null_reason`
- `derivation_method`
- `assumptions`
- `provenance`

`input_source` は絶対ローカルpathを返しません。`input_hash` と `provenance.input_hash` は同じmaterialized artifactを指します。forecast itemにはそのrunで読み込んだmaterialized assumptionsを明示し、actual itemでは仮定を勝手に生成しません。

未materialize、欠損、計算不能は0へ変換せず `null_reason` / `null_reasons` でfail-closeします。`get_data_freshness` と `get_audit_diff` も独立したcanonical ID、hash、生成時点、derivationを返します。

External API responsesは source ID、sanitized request URL、retrieval timestamp、HTTP status、content type、raw SHA-256を保持し、credential値をprovenanceへ混入させません。

## CI contract

`.github/workflows/mcp-contract.yml` は以下をblocking gateとして実行します。

1. Python syntax
2. Ruff
3. MCP tool discovery
4. actual / forecast分離
5. dashboard / domain / MCP計算parity
6. null-not-zero
7. provenance必須fieldとSHA-256
8. absolute private path / credential非公開
9. missing dataset / stale dataのfail-close
10. private operational fileのgitignore契約
11. runtime cacheを除去した後の `git status --porcelain --untracked-files=all` が空であること

## EDINET DB boundary

個人家計・資産の core contract には EDINET DB を自動接続しません。上場企業分析が必要な別ユースケースから明示的に呼ぶ場合だけ利用し、家計 BS/PL/CF の必須依存にはしません。
