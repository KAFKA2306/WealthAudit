# Source Adapter contract

Issue #10 defines one boundary for future bank, broker and card collectors.

```text
authenticate -> fetch raw -> parse -> normalize -> validate -> handoff
```

`SourceAdapter` implementations may contain provider-specific authentication and field mapping. They must not calculate BS/PL/CF values. The only normalized handoff tables are the existing `income`, `expense`, `assets` and `market` inputs described in `docs/logics/input.md`.

## Fail-closed rules

Before handoff, the shared validator rejects:

- provider-specific/unknown output tables;
- missing canonical fields;
- records outside the requested month;
- duplicate canonical identities within a table;
- unknown `account_id` values in income/assets;
- unknown `method_id` values in expenses.

A failed fetch/parse/normalize/validate call raises and therefore produces no successful `AdapterResult`. Callers must only update a target month after a complete result has been validated; previously closed months are outside the adapter's write responsibility.

## Provenance

Every successful run records non-secret metadata:

- source ID;
- retrieval timestamp;
- target month;
- normalized record count;
- SHA-256 of the raw fetched bytes.

`write_provenance()` writes this metadata atomically. Runtime metadata belongs below `data/`, which is Git-ignored. Raw downloads, HTML dumps, cookies, passwords, passkeys and tokens are not accepted by the provenance writer and must never be committed.

## Adding a real source

A production adapter must implement all five stages and document the provider's official API/export terms before it is enabled. Do not add demo adapters to production code; tests may use local fixture subclasses. A provider integration is a separate change from this contract and must not weaken the canonical validation rules.
