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
| `forecast.csv` | **Primary data source for all graphs** (history + 30-year projection) | All columns from cashflow, balance_sheet, metrics |
| `cashflow.csv` | Cash Flow Statement (legacy) | `month`, `after_tax_income`, `expenditure`, `net_savings` |
| `balance_sheet.csv` | Balance Sheet (legacy) | `month`, `liquid_assets`, `risk_assets`, `pension_assets`, `total_financial_assets`, `investment_gain_loss` |
| `metrics.csv` | Financial Metrics (legacy) | `month`, `savings_rate`, `risk_asset_ratio`, `monthly_return`, `monthly_alpha` |

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
- **Data Source**: `forecast.csv` (Time series).
- **X-Axis**: `month`
- **Y-Axis**: 
    - `after_tax_income` (Positive Bar, Green)
    - `expenditure` (Negative Bar, Red)
    - `investment_gain_loss` (Bar, Purple)
    - `total_flow` = `net_savings + investment_gain_loss` (Line, Blue)
- **Moving Averages**: 12-month (Income, Total Flow)
- **Reference**: See [bsplcf.md](../logics/bsplcf.md) for calculation logic.

### D. Financial Ratios (Line Chart)
- **Data Source**: `metrics.csv`.
- **Metrics**: 
    - `savings_rate` (%)
    - `risk_asset_ratio` (%)
- **Unit**: Percentage (0-100%).

### E. Investment Returns (Line Chart)
- **Data Source**: `metrics.csv`.
- **Metrics**: 
    - `monthly_return` (ROI %)
    - `benchmark_return` (S&P 500 JPY %)
    - `monthly_alpha` (Excess Return %)
- **Unit**: Percentage (typically +/- 10%).

### F. Financial Independence (FI) Ratios (Line Chart)
- **Data Source**: `metrics.csv`.
- **Metrics**: 
    - `fi_ratio_12m` (Trailing 12m)
    - `fi_ratio_48m` (Trailing 48m)
    - `fi_ratio_next_12m` (Projected)
- **Unit**: Ratio (Multiple of Expenses). Target is typically 25x.

## 5. Implementation Pattern

### Endpoint Structure (Example)
```html
<!-- Container -->
<div id="graph-container" hx-get="/graphs/net-worth" hx-trigger="load">
    <!-- Graph will be injected here -->
    <div class="spinner">Loading...</div>
</div>

<!-- Controls -->
<button hx-get="/graphs/net-worth?months=12" hx-target="#graph-container">1Y</button>
<button hx-get="/graphs/net-worth" hx-target="#graph-container">All</button>
<button hx-get="/graphs/net-worth?forecast=60" hx-target="#graph-container">+5Y</button>
```

### Backend Logic
The backend handler should:
1. Load CSV data from `data/calculated/` using repositories.
2. Filter DataFrame based on query params (e.g., `range`).
3. Generate Plotly Figure.
4. Return `fig.to_html(full_html=False, include_plotlyjs='cdn')`.

### File Structure (Implemented)
```
src/
├── infrastructure/
│   └── web.py              # Flask server with HTMX endpoints
├── use_cases/
│   └── graph_service.py    # Plotly chart generation
└── domain/
    └── entities/           # Data models (BalanceSheet, CashFlowStatement, etc.)

templates/
├── dashboard.html          # Main dashboard with HTMX
└── input.html              # Data entry form
```

## 6. Forecast Toggle Feature

将来予測データの表示/非表示を切り替える機能。

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `months` | int | 過去Nヶ月のデータを表示（例: `?months=12`）|
| `forecast` | int | 現在月からNヶ月先までの予測を表示（例: `?forecast=60`）|

### Usage Examples

```html
<!-- 過去1年 -->
<button hx-get="/graphs/net-worth?months=12">1Y</button>

<!-- 全履歴（実績のみ）-->
<button hx-get="/graphs/net-worth">All</button>

<!-- 将来5年予測 -->
<button hx-get="/graphs/net-worth?forecast=60">+5Y</button>

<!-- 将来10年予測 -->
<button hx-get="/graphs/net-worth?forecast=120">+10Y</button>
```

### Data Source

- 予測データは `data/calculated/forecast.csv` から取得
- 30年分（360ヶ月）の予測データが含まれる
- 詳細は [forecast.md](../logics/forecast.md) 参照

## 7. Implementation Status

All proposed graphs are implemented:
- ✅ Net Worth Trend (stacked bar)
- ✅ Cash Flow (bar chart with 6-month moving average)
- ✅ Asset Allocation (100% stacked bar)
- ✅ Financial Ratios (line chart)
- ✅ Investment Returns (line chart)
- ✅ FI Ratios (line chart)
- ✅ Forecast Toggle (+5Y buttons)
