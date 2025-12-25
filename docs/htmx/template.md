# Dashboard Template

The dashboard uses HTMX for dynamic content loading without custom JavaScript.

## Location

[templates/dashboard.html](file:///wsl.localhost/Ubuntu-22.04-LTS/home/kafka/finance/bspl/templates/dashboard.html)

## Features

- **Dark Theme**: Modern dark color scheme with gradient background
- **Responsive Grid**: 2-column layout, collapses to 1 column on mobile
- **HTMX Loading**: Charts load asynchronously on page load
- **Filter Buttons**: 1Y / All range selectors for time-series charts

## HTMX Patterns Used

### Auto-load on Page Load
```html
<div id="graph" hx-get="/graphs/net-worth" hx-trigger="load">
    <span class="spinner">Loading</span>
</div>
```

### Button-triggered Filtering
```html
<button hx-get="/graphs/net-worth?months=12" hx-target="#graph">1Y</button>
```

## CSS Variables

```css
:root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-card: #334155;
    --text-primary: #f8fafc;
    --accent-blue: #3b82f6;
    --accent-green: #10b981;
    --accent-purple: #8b5cf6;
}
```

## Layout Structure

```
dashboard
├── header (title, subtitle)
└── grid (2x2)
    ├── Net Worth Trend
    ├── Cash Flow
    ├── Asset Allocation
    └── Financial Metrics
```
