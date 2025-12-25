# Household Financial Statement Calculator

## Overview
This is a Python-based application designed to calculate and analyze household financial statements. It processes transaction and asset data to generate:
- **Cash Flow Statement**: Monthly income, expenditure, and net savings.
- **Balance Sheet**: Monthly assets (liquid, risk, pension) and investment performance.
- **Metrics**: Key financial indicators such as savings rate, risk asset ratio, and monthly investment returns (including alpha against benchmarks).

## Features
- **Automated Calculations**: Generates BS/PL from raw CSV data.
- **Investment Tracking**: Calculates investment profit/loss and compares performance against market benchmarks (e.g., S&P 500).
- **Dependency Injection**: Built with clean architecture principles using `injector`.

## Requirements
- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) (for dependency management)
- [go-task](https://taskfile.dev/) (optional, for running tasks)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd bspl
   ```

2. Install dependencies:
   ```bash
   task setup
   # OR
   uv sync
   ```

## Usage

### Prepare Data
Place your source CSV files (transactions, assets, market data) in the appropriate data directories (configured in repositories).

### Run Calculations
Execute the main application to process data and generate reports:

```bash
task run
# OR
uv run python -m src.infrastructure.cli
```

### Outputs
Calculated files are exported to `data/calculated/`:
- `cashflow.csv`: Monthly income and savings.
- `balance_sheet.csv`: Asset breakdown and investment gains.
- `metrics.csv`: Financial performance indicators.

## Development

- **Run Tests**: `task test`
- **Lint Code**: `task lint`
- **Format Code**: `task format`

## Documentation
See `docs/` for detailed logic specifications (Japanese).
