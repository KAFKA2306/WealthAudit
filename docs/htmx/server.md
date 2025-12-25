# Flask Web Server

The web server provides HTMX endpoints for the financial dashboard.

## Location

[src/infrastructure/web.py](file:///wsl.localhost/Ubuntu-22.04-LTS/home/kafka/finance/bspl/src/infrastructure/web.py)

## Endpoints

| Method | Route | Query Params | Description |
|--------|-------|--------------|-------------|
| GET | `/` | - | Dashboard HTML page |
| GET | `/graphs/net-worth` | `months` | Net worth stacked area chart |
| GET | `/graphs/cashflow` | `months` | Income/expense bar chart |
| GET | `/graphs/allocation` | - | Asset allocation donut chart |
| GET | `/graphs/metrics` | `months` | Savings rate & alpha line chart |

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
