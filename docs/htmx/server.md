# Flask Web Server

The web server provides HTMX endpoints for the financial dashboard.

## Location

[src/infrastructure/web.py](file:///wsl.localhost/Ubuntu-22.04-LTS/home/kafka/finance/bspl/src/infrastructure/web.py)

## Endpoints

| Method | Route | Query Params | Description |
|--------|-------|--------------|-------------|
| GET | `/` | - | Dashboard HTML page |
| GET/POST | `/input` | - | Data entry form (income, expense, assets, market) |
| GET | `/graphs/net-worth` | `months` | Net worth stacked bar chart |
| GET | `/graphs/cashflow` | `months` | Income/expense bar chart (6-month moving average) |
| GET | `/graphs/allocation` | `months` | Asset allocation trend (100% stacked bar) |
| GET | `/graphs/ratios` | `months` | Savings rate & risk asset ratio |
| GET | `/graphs/returns` | `months` | Investment returns & alpha |
| GET | `/graphs/fi` | `months` | Financial Independence ratios |

## Query Parameters

| Param | Type | Description |
|-------|------|-------------|
| `months` | int | Optional. Filter to last N months |

## Example Requests

```bash
# Full page
curl http://localhost:5000/

# Net worth (last 12 months)
curl http://localhost:5000/graphs/net-worth?months=12

# Asset allocation (current)
curl http://localhost:5000/graphs/allocation
```

## Running the Server

```bash
task serve
# OR
uv run python -m src.infrastructure.web
```

Default: `http://localhost:5000`
