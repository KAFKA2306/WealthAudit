# Financial Metrics Logic

The executable source of truth for metric equations is
`src/use_cases/calculators/formula_manifest.py`. This document names the contracts and explains the
windowing rules without copying equation strings into a second hand-maintained location.

`MetricsCalculator` evaluates these manifest entries directly:

- `savings_rate_12m`
- `risk_asset_ratio`
- `raw_monthly_return`
- `monthly_alpha`
- `fi_ratio_12m`
- `fi_ratio_48m`
- `fi_ratio_next_12m`

## Windowing rules

Savings rate and the 12-month FI ratio use the trailing 12 calendar months ending at the metric
month. The 48-month FI ratio uses the trailing 48 calendar months. Missing months do not create
synthetic cash-flow or balance-sheet rows; only available rows in the selected calendar window are
summed.

Portfolio and benchmark trend returns retain the existing geometric-mean implementation in
`metrics.py`: raw finite monthly returns greater than -100% are compounded over the trailing 12
calendar-month positions. This windowing algorithm is intentionally separate from the scalar Formula
Manifest because its input is a time series rather than named scalar operands.

## Audit path

Open `/static/calculation-inspector.html` while the local Flask app is running. The Formula cards are
generated from the canonical manifest and the lower section loads current calculated tables through
the same GraphService endpoints used by the dashboard. No financial formula is reimplemented in the
HTML.

`tests/test_formula_manifest.py` verifies manifest evaluation, raw-before-rounding trace retention,
zero-denominator policy, and byte-for-byte synchronization between the generated Inspector and the
checked-in static artifact.
