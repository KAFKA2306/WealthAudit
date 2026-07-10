# System Architecture

## Data Flow Pipeline

```mermaid
sequenceDiagram
    participant User
    participant Drive as Google Drive XLSX
    participant Web as Flask/HTMX
    participant FS as CSV Files
    participant Task as go-task

    User->>Drive: Edit workbook
    Drive->>FS: Sync XLSX boundary to data/input/*.csv
    User->>Web: POST /input
    Web->>FS: Update data/input/*.csv
    Web->>Task: task run
    Task->>FS: Write cashflow/balance_sheet/metrics
    Web->>Task: task export
    Task->>FS: Write normalized.csv
    Web->>Task: task forecast
    Task->>FS: Write forecast.csv and forecast_annual.csv
    Web->>User: Render dashboard
```

## Boundaries

- `src/infrastructure/web.py`: Flask + HTMX routes, CSV updates, task triggers.
- `Taskfile.yml`: `run`, `export`, `forecast`.
- `scripts/forecast.py`: `normalized.csv` + `master/forecast_streams.csv` → forecast CSVs.
- `data/input/`: source CSVs.
- `data/calculated/`: generated CSVs.
- `master/`: account, asset, payment, forecast stream metadata.
