from pathlib import Path

import math

from scripts.generate_calculation_inspector import render
from src.use_cases.calculators.formula_manifest import (
    FORMULA_MANIFEST,
    evaluate_formula,
    trace_formula,
)


def test_core_causal_chain_uses_manifest() -> None:
    net_savings = evaluate_formula(
        "net_savings", {"after_tax_income": 500_000, "expenditure": 300_000}
    )
    contribution = evaluate_formula(
        "net_worth_contribution",
        {"net_savings": net_savings, "asset_contribution": 50_000},
    )
    gain = evaluate_formula(
        "investment_gain_loss",
        {
            "current_total_financial_assets": 10_500_000,
            "previous_total_financial_assets": 10_000_000,
            "net_worth_contribution": contribution,
        },
    )
    assert net_savings == 200_000
    assert contribution == 250_000
    assert gain == 250_000


def test_trace_keeps_pre_round_value_and_display_value() -> None:
    trace = trace_formula(
        "savings_rate_12m",
        {"net_savings_12m": 1, "after_tax_income_12m": 3},
        digits=4,
    )
    assert trace.raw_result == 1 / 3
    assert trace.rounded_result == 0.3333
    assert trace.formula.unit == "ratio"
    assert tuple(trace.inputs) == FORMULA_MANIFEST["savings_rate_12m"].inputs


def test_zero_denominator_contract_is_explicit() -> None:
    assert evaluate_formula(
        "savings_rate_12m", {"net_savings_12m": 1, "after_tax_income_12m": 0}
    ) == 0.0
    result = evaluate_formula(
        "raw_monthly_return",
        {"investment_gain_loss": 1, "return_base_assets": 0},
    )
    assert math.isnan(result)


def test_generated_inspector_is_exact_manifest_artifact() -> None:
    artifact = Path("static/calculation-inspector.html").read_text(encoding="utf-8")
    assert artifact == render()
    for formula_id, spec in FORMULA_MANIFEST.items():
        assert f"id='formula-{formula_id}'" in artifact
        assert spec.formula in artifact
        assert spec.source in artifact
    assert "hx-get='/graphs/net-worth?months=2'" in artifact
    assert "hx-get='/graphs/cashflow?months=2'" in artifact
