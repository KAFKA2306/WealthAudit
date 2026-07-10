# ADR 0001: Drive-Synced XLSX as the Cloud Boundary

Date: 2026-07-09
Decision Status: Accepted

## Context

WealthAudit currently treats local CSV files as the data source:

- `data/input/*.csv`: user-maintained source data
- `data/calculated/*.csv`: generated outputs
- local Flask/HTMX UI: dashboard and manual input

The desired operating model is:

- avoid data loss by using cloud sync
- keep the workflow easy enough for one user
- avoid Google Cloud Console setup, OAuth consent screens, service accounts, API keys, and credential files
- allow Google Sheets-style viewing and input
- do not anonymize account names or asset labels
- do not expose the Flask app to the public internet

## Decision

Use a Google Drive for desktop synced `.xlsx` file as the cloud boundary.

```text
Google Drive for desktop
  -> Drive-synced WealthAudit/input.xlsx
  -> local WealthAudit import
  -> data/input/*.csv
  -> task run/export/forecast
  -> Drive-synced WealthAudit/view.xlsx
```

Google Sheets API will not be used for the default workflow.

Google Sheets may be used by opening the Drive-hosted `.xlsx` file in the browser, but WealthAudit itself reads and writes local files only.

## Scope

The default synced files are:

- `input.xlsx`: human-editable workbook for `income`, `expense`, `assets`, and `market`
- `view.xlsx`: generated workbook for dashboard-friendly summaries
- optional backup files under a Drive-synced `backup/` directory

The canonical application source remains:

- `data/input/income.csv`
- `data/input/expense.csv`
- `data/input/assets.csv`
- `data/input/market.csv`

The Drive workbook is an operational input and sync surface, not the internal calculation database.

## Rationale

This avoids the human setup burden of:

- Google Cloud projects
- OAuth client registration
- service account sharing
- API scopes
- credential JSON files
- token refresh handling

It also matches the current WealthAudit implementation, which already reads and writes local CSV files and has no authentication layer in the Flask server.

Cloud durability is delegated to Google Drive for desktop. Authentication is delegated to the user's Google account and local OS session.

## Security Boundary

The security boundary is:

```text
Google account authentication
  + local OS account
  + non-shared Drive files
  + local-only WealthAudit server
```

The following are required operational constraints:

- keep Drive files private and unshared
- keep the Flask app bound to localhost only
- keep `data/` out of Git
- do not store passwords, API tokens, recovery phrases, or brokerage credentials in `.xlsx`, CSV, Markdown, or Git
- use Google account passkey or 2-step verification

Account names and asset labels may remain human-readable. This ADR explicitly does not require anonymization.

## Consequences

Positive:

- no Google API credential management
- low human setup burden
- browser-based spreadsheet input remains possible
- local CSV pipeline remains auditable
- cloud sync reduces local disk loss risk

Negative:

- `.xlsx` sync can have conflict files if edited concurrently from multiple devices
- Google Drive sync state must be trusted and monitored
- Google Sheets-specific formulas or features may not round-trip perfectly through `.xlsx`
- this is not a zero-knowledge storage design

## Implementation Notes

The local Drive boundary is operated through these tasks:

- import `input.xlsx` into `data/input/*.csv`
- export `data/calculated/forecast.csv` or summary data into `view.xlsx`
- detect or configure the Drive sync directory
- add a single `task sync-drive` command
- verify local readiness with `task drive:doctor`
- snapshot operational files with `task drive:backup`
- restore from an explicit backup with `task drive:restore -- --backup-dir <path>`
- keep the Flask server local-only

The implementation should prefer boring local file conversion over any API integration.
