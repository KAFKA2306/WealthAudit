# WealthAudit local MCP + official external APIs

WealthAudit の MCP は `127.0.0.1` に固定した read-only gateway です。家計・資産の raw input を公開せず、既存の計算結果と、allow-list 済みの公式外部 API だけを読み出します。外部 API は **データ取得源**であり、BS/PL/CF や FI 指標の計算エンジンではありません。

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

## Provenance

Local financial responses retain period, actual/forecast, derivation method, relative input source, SHA-256, generated time and null reason semantics. External API responses add source ID, sanitized request URL, retrieval timestamp, HTTP status, content type and raw SHA-256.

## EDINET DB boundary

個人家計・資産の core contract には EDINET DB を自動接続しません。上場企業分析が必要な別ユースケースから明示的に呼ぶ場合だけ利用し、家計 BS/PL/CF の必須依存にはしません。
