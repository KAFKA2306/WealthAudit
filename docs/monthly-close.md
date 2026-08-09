# Monthly close state machine

The canonical monthly BS/PL/CF update is exactly one state machine:

```text
collect -> normalize -> calculate -> audit -> close
```

`src/use_cases/monthly_close.py` owns the transition order and the rule that `close` is reachable only after `audit=PASS`. Web and CLI entry points use the same `MonthlyCloseWorkflow`; infrastructure code only supplies filesystem and command adapters.

## State contract

| State | Input | Output | Failure condition |
| --- | --- | --- | --- |
| `collect` | target month and prepared private input CSVs | staged `data/input` | input cannot be staged |
| `normalize` | staged input CSVs | validated canonical input tables | required file/column is missing or a month is empty |
| `calculate` | validated private inputs | calculated BS/PL/CF, normalized export, forecast | any low-level `task run`, `task export`, or `task forecast` command fails |
| `audit` | calculated outputs | `PASS` or `FAIL` | `task audit:recalculate` fails, recalculation is non-deterministic, or the target month is not represented exactly once in each core calculated table |
| `close` | `audit=PASS` plus SHA-256 input fingerprint | runtime close marker | marker cannot be written atomically |

On any failure after processing starts, both private inputs and calculated outputs are restored to their pre-run snapshots. `close` is never called after `audit=FAIL`.

## Idempotency

The adapter computes a SHA-256 fingerprint from the prepared private input CSV set. A successful close stores only the month, fingerprint, audit status, and completed state names under `data/state/monthly-close.json`. `data/` is gitignored. Re-running the same month with the same input fingerprint returns the prior PASS without recalculation, so it cannot append duplicate month rows.

A changed input fingerprint starts a fresh transaction. If that run fails, the previous inputs and calculated outputs are restored.

## Entry points

CLI:

```bash
task monthly-close -- 2026-07
```

If the month is omitted, the CLI uses the latest month present in private `data/input/income.csv`.

The Web `/input` POST builds the replacement rows for one month and passes those prepared tables to the same `MonthlyCloseWorkflow`.

Low-level tasks remain available for development and diagnostics:

- `task run`: calculate core cash-flow, balance-sheet, and metrics CSVs only.
- `task export`: build the normalized export only.
- `task forecast`: build forecast outputs only.
- `task audit:recalculate`: deterministic before/after recalculation audit used by the canonical `audit` state; it is not an independent close path.

Operational monthly updates should use `task monthly-close`, `task sync-drive`, or the Web input form rather than manually chaining the low-level tasks.

## Repository boundary

Operational CSVs, close markers, authentication material, browser/session data, and backups remain outside Git because `data/`, XLSX operational files, and backup paths are ignored by `.gitignore`.
