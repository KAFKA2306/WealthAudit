# Graphing Architecture (HTMX Integration)

This document outlines the strategy for visualizing financial components using HTMX and Python-based plotting libraries.

## 1. Objectives
- **Visual Analysis**: Provide intuitive charts for Balance Sheets, Cash Flows, and Asset Allocation.
- **Interactivity**: Allow users to filter by range (e.g., "Last 12 Month", "YTD", "All Time") without full page reloads.
- **Simplicity**: Maintain server-side rendering preference where possible, leveraging HTMX for dynamic updates.

## 2. Technology Stack
- **Frontend**: HTMX for fetching graph fragments.
- **Backend**: Python (e.g., FastAPI/Flask or local CLI serving HTML).
- **Plotting Library**: 
    - **Plotly**: Recommended for interactive HTML output.
    - **Matplotlib/Seaborn**: Good for static images/SVG, but less interactive.
    - **Recommendation**: Use **Plotly** to generate HTML fragments (`<iframe>` or `<div>`) that HTMX can inject.

## 3. Data Sources

All data originates from CSV files as defined in [schemas.md](../domain/schemas.md) and [input.md](../logics/input.md).

### Input Files (`data/input/`)
| File | Description | Key Columns |
|------|-------------|-------------|
| `income.csv` | Monthly income records | `month`, `account_id`, `amount` |
| `expense.csv` | Monthly expense records | `month`, `method_id`, `amount` |
| `assets.csv` | Monthly asset balances | `month`, `account_id`, `asset_class`, `balance` |
| `market.csv` | Market data (FX, indices) | `month`, `usd_jpy`, `eur_jpy`, `sp500` |

### Calculated Files (`data/calculated/`)
| File | Description | Key Columns |
|------|-------------|-------------|
| `cashflow.csv` | Cash Flow Statement | `month`, `income`, `expenses`, `net_savings` |
| `balance_sheet.csv` | Balance Sheet | `month`, `liquid_assets`, `risk_assets`, `pension_assets`, `total_financial_assets`, `investment_gain_loss` |
| `metrics.csv` | Financial Metrics | `month`, `savings_rate`, `risk_asset_ratio`, `monthly_return`, `monthly_alpha` |

### Master Files (`master/`)
| File | Description | Key Columns |
|------|-------------|-------------|
| `accounts.csv` | Account master | `account_id`, `name`, `type`, `currency`, `risk` |
| `payment_methods.csv` | Payment method master | `method_id`, `name`, `settlement_account` |

## 4. Proposed Graphs

### A. Asset Allocation (Pie/Donut Chart)
- **Data Source**: `balance_sheet.csv` (Latest month).
- **Dimensions**: 
    - `liquid_assets`
    - `risk_assets`
    - `pension_assets`
- **HTMX Trigger**: Load on page load or when specific month is selected.

### B. Net Worth Trend (Stacked Area/Line Chart)
- **Data Source**: `balance_sheet.csv` (Time series).
- **X-Axis**: `month`
- **Y-Axis**: `total_financial_assets` (Stacked by `liquid_assets`, `risk_assets`, `pension_assets`).
- **Interaction**: Date range selector triggered via `hx-get="/graphs/net-worth?range=..."` targeting the graph container.

### C. Monthly Cash Flow (Bar Chart)
- **Data Source**: `cashflow.csv` (Time series).
- **X-Axis**: `month`
- **Y-Axis**: 
    - `income` (Positive Bar)
    - `expenses` (Negative Bar)
    - `net_savings` (Line overlay or Separate Bar)
- **Reference**: See [bsplcf.md](../logics/bsplcf.md) for calculation logic.

### D. Investment Performance (Line Chart)
- **Data Source**: `metrics.csv`, `balance_sheet.csv`.
- **Metrics** (from [metrics.md](../logics/metrics.md)): 
    - `investment_gain_loss` (Cumulative)
    - `monthly_return` (ROI %)
    - `monthly_alpha` (vs S&P 500 benchmark)

### E. Savings Rate Trend (Line/Bar Chart)
- **Data Source**: `metrics.csv`.
- **X-Axis**: `month`
- **Y-Axis**: `savings_rate` (%)
- **Goal Line**: Optional target (e.g., 30%)

### F. Risk Asset Ratio Trend (Line/Area Chart)
- **Data Source**: `metrics.csv`.
- **X-Axis**: `month`
- **Y-Axis**: `risk_asset_ratio` (%)
- **Reference**: Indicates portfolio risk exposure over time.

## 5. Implementation Pattern

### Endpoint Structure (Example)
```html
<!-- Container -->
<div id="graph-container" hx-get="/graphs/net-worth" hx-trigger="load">
    <!-- Graph will be injected here -->
    <div class="spinner">Loading...</div>
</div>

<!-- Controls -->
<button hx-get="/graphs/net-worth?range=12m" hx-target="#graph-container">1Y</button>
<button hx-get="/graphs/net-worth?range=all" hx-target="#graph-container">All</button>
```

### Backend Logic
The backend handler should:
1. Load CSV data from `data/calculated/` using repositories.
2. Filter DataFrame based on query params (e.g., `range`).
3. Generate Plotly Figure.
4. Return `fig.to_html(full_html=False, include_plotlyjs='cdn')`.

### File Structure (Proposed)
```
src/
├── infrastructure/
│   └── web.py          # HTMX server endpoints
├── application/
│   └── graph_service.py  # Graph generation logic
└── domain/
    └── entities/        # Existing models (BalanceSheet, CashFlowStatement, etc.)
```

## 6. Next Steps
1. Prototype a simple web server (e.g., `src/infrastructure/web.py`) if not already present.
2. Implement `/graphs/*` endpoints for each proposed graph.
3. Design a dashboard template with HTMX controls.
4. Add graph generation tests.
