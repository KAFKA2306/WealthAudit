# HTMX Dashboard Overview

This directory documents the HTMX-powered financial dashboard implementation.

## Documentation

| Document | Description |
|----------|-------------|
| [graph.md](./graph.md) | Graphing architecture and data sources |
| [server.md](./server.md) | Flask web server endpoints |
| [template.md](./template.md) | Dashboard HTML/CSS template |

## Quick Start

```bash
cd /home/kafka/finance/bspl
uv sync          # Install dependencies
task serve       # Start http://localhost:5000
```

## Architecture

```
src/
├── use_cases/
│   └── graph_service.py    # Chart generation (Plotly)
└── infrastructure/
    └── web.py              # Flask server

templates/
└── dashboard.html          # HTMX UI
```

## Technology Stack

- **HTMX**: Dynamic content loading without JavaScript
- **Flask**: Lightweight Python web framework
- **Plotly**: Interactive chart library
