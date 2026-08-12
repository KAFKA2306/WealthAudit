# Canonical WealthAudit flow

WealthAudit keeps one decision path:

```text
private account / position / transaction inputs
  -> validated domain records
  -> calculation / valuation use-cases
  -> data/calculated private outputs
  -> audit checks
  -> local dashboard / export
```

## Source of truth

- Account and classification definitions: `master/`
- Private observations and transactions: `data/input/` (Git ignored)
- Calculation and valuation logic: `src/domain/` and `src/use_cases/`
- Private derived outputs: `data/calculated/` (Git ignored)
- User-facing projection: `src/infrastructure/web.py` and `templates/`

The dashboard, XLSX export, and MCP/API-facing projections must not become independent financial ledgers. Unknown, stale, or unavailable values remain explicit rather than being silently filled.

## Security boundary

Private account metadata, balances, transactions, credentials, `input.xlsx`, `view.xlsx`, backups, and generated private datasets are not public repository artifacts. External JavaScript/API dependencies must be justified and version-pinned when they are required for the local product path.

## Ratchet KPIs

Only these three repository-level KPIs are canonical for this ratchet:

1. **freshness** — whether required financial observations satisfy the declared freshness contract.
2. **integrity pass rate** — whether account/position/transaction/valuation inputs pass schema, reference, duplicate, and calculation checks.
3. **manual corrections** — explicit human corrections required after import/recalculation; `unknown` is not converted to zero.

## Non-goals

- Adding another ledger or aggregation layer.
- Treating a public dashboard artifact as authoritative financial data.
- Adding recurring research automation unrelated to the account → valuation → audit → decision path.
