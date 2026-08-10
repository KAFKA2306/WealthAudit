# Local read-only MCP

WealthAuditのMCPは、個人資産データを外部公開せず、既存のローカル計算結果を読み出すためのadapterです。EDINET DBは使用しません。

## Privacy boundary

- bind先はコード上 `127.0.0.1` に固定
- `0.0.0.0` や任意host指定は初期実装では提供しない
- `data/`, `input.xlsx`, `view.xlsx`, `backup/` は既存 `.gitignore` を維持
- MCP responseへ絶対パスを返さない
- raw input workbook/CSVを返さない
- write/mutation toolなし
- secret/tokenをtool引数やresponseへ載せない

`WEALTHAUDIT_ROOT` は、ローカルで計算済み `data/calculated/` を含むrepository rootを指定するためだけに使用します。responseでは相対artifact名とSHA-256だけを返します。

## Start

```bash
python -m pip install -e '.[mcp]'
python -m src.interface_adapters.mcp_server
```

既定endpointはloopback上のStreamable HTTPです。

## Tools

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

## Shared calculation rule

MCPは家計計算を独自実装しません。

- BS/returns/FI/forecast: `scripts/forecast.py` がmaterializeした `data/calculated/forecast.csv` を読む
- cash-flow reconciliation: 既存 `src.use_cases.graph_service.total_wealth_flow` を再利用
- asset allocation: dashboardの `GraphService` と同じallocation table calculationを再利用
- recalculation diff: `scripts/recalculate_audit.py` が生成する `recalculation_diff.csv` を読む

## Actual / forecast

`forecast.csv:is_forecast` を正本とし、各rowに `actual_or_forecast=actual|forecast` を付与します。期間未指定の主要toolは最新actualを返し、将来rowへ自動的にフォールバックしません。

`null`、NaN、未materialize列は0へ変換しません。`values[field]=null` と `null_reasons[field]` を返します。

## Provenance

数値responseは該当範囲で以下を返します。

- period
- actual_or_forecast
- derivation_method
- relative `input_source`
- SHA-256 `input_hash`
- generated_at（artifact mtimeをUTC化）
- null_reasons

絶対パスは返しません。

## Freshness / warnings

`get_data_freshness` は最新actual monthと完了月を比較します。`get_warnings` は少なくとも次をfail-closeで表現します。

- calculated dataset absent
- duplicate month
- actual rows absent
- latest actual stale
- latest actual contains null

## EDINET DB boundary

中央registryでは `KAFKA2306/WealthAudit` を `not_applicable` としています。個人家計・資産のcurrent contractに上場企業財務は不要なため、EDINET DBへのdirect fallbackもquota-owner projectionも追加しません。

中央policy: https://github.com/KAFKA2306/semiconductor-earnings-model/blob/main/docs/edinetdb-consumer-registry.md
