# Balance Sheet and Cash Flow Logic

The canonical calculation contract is `src/use_cases/calculators/formula_manifest.py`.
This document intentionally does not duplicate executable equations. Formula text, input names,
units, and source references are rendered from that manifest into the Calculation Inspector.

## Cash Flow

`CashFlowCalculator` aggregates monthly income, pension contributions, and expenditure, then evaluates:

- `net_savings`
- `net_worth_contribution`

through the canonical manifest evaluator.

## Balance Sheet

`BalanceSheetCalculator` values and classifies assets, then evaluates:

- `total_financial_assets`
- `investment_gain_loss`
- `return_base_assets`

through the same manifest evaluator. `investment_gain_loss` is only evaluated for consecutive months;
otherwise the existing zero/default behavior is preserved.

## Inspection and audit

Open `/static/calculation-inspector.html` while the local Flask app is running. The page itself is a
generated artifact from the manifest and uses the existing GraphService endpoints for current
calculated tables. It performs no accounting arithmetic in HTML/JavaScript.

`tests/test_formula_manifest.py` locks the causal chain, pre-round values, zero-denominator behavior,
and exact generated-HTML synchronization. `.github/workflows/formula-manifest.yml` regenerates the
Inspector and fails when the checked-in artifact differs from the manifest.
