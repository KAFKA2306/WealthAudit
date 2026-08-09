from __future__ import annotations

import math
from dataclasses import dataclass
from functools import reduce
from operator import mul
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FormulaSpec:
    id: str
    label: str
    formula: str
    inputs: tuple[str, ...]
    unit: str
    source: str
    operation: str
    empty_division_result: float = 0.0


@dataclass(frozen=True)
class CalculationTrace:
    formula: FormulaSpec
    inputs: Mapping[str, float]
    raw_result: float
    rounded_result: float | int


FORMULA_MANIFEST: dict[str, FormulaSpec] = {
    "net_savings": FormulaSpec(
        id="net_savings",
        label="純貯蓄",
        formula="after_tax_income - expenditure",
        inputs=("after_tax_income", "expenditure"),
        unit="JPY/month",
        source="data/calculated/cashflow.csv",
        operation="subtract",
    ),
    "net_worth_contribution": FormulaSpec(
        id="net_worth_contribution",
        label="純資産への拠出",
        formula="net_savings + asset_contribution",
        inputs=("net_savings", "asset_contribution"),
        unit="JPY/month",
        source="data/calculated/cashflow.csv",
        operation="sum",
    ),
    "total_financial_assets": FormulaSpec(
        id="total_financial_assets",
        label="総金融資産",
        formula="liquid_assets + risk_assets + pension_assets",
        inputs=("liquid_assets", "risk_assets", "pension_assets"),
        unit="JPY",
        source="data/calculated/balance_sheet.csv",
        operation="sum",
    ),
    "investment_gain_loss": FormulaSpec(
        id="investment_gain_loss",
        label="投資損益",
        formula="current_total_financial_assets - previous_total_financial_assets - net_worth_contribution",
        inputs=(
            "current_total_financial_assets",
            "previous_total_financial_assets",
            "net_worth_contribution",
        ),
        unit="JPY/month",
        source="data/calculated/balance_sheet.csv + data/calculated/cashflow.csv",
        operation="subtract",
    ),
    "return_base_assets": FormulaSpec(
        id="return_base_assets",
        label="投資リターン計算元本",
        formula="previous_risk_assets + previous_pension_assets",
        inputs=("previous_risk_assets", "previous_pension_assets"),
        unit="JPY",
        source="data/calculated/balance_sheet.csv",
        operation="sum",
    ),
    "savings_rate_12m": FormulaSpec(
        id="savings_rate_12m",
        label="12か月貯蓄率",
        formula="net_savings_12m / after_tax_income_12m",
        inputs=("net_savings_12m", "after_tax_income_12m"),
        unit="ratio",
        source="data/calculated/metrics.csv + data/calculated/cashflow.csv",
        operation="divide",
    ),
    "risk_asset_ratio": FormulaSpec(
        id="risk_asset_ratio",
        label="リスク資産比率",
        formula="risk_and_pension_assets / total_financial_assets",
        inputs=("risk_and_pension_assets", "total_financial_assets"),
        unit="ratio",
        source="data/calculated/metrics.csv + data/calculated/balance_sheet.csv",
        operation="divide",
    ),
    "raw_monthly_return": FormulaSpec(
        id="raw_monthly_return",
        label="月次投資リターン（生値）",
        formula="investment_gain_loss / return_base_assets",
        inputs=("investment_gain_loss", "return_base_assets"),
        unit="ratio/month",
        source="data/calculated/metrics.csv + data/calculated/balance_sheet.csv",
        operation="divide_nan",
        empty_division_result=math.nan,
    ),
    "monthly_alpha": FormulaSpec(
        id="monthly_alpha",
        label="月次アルファ",
        formula="monthly_return - benchmark_return",
        inputs=("monthly_return", "benchmark_return"),
        unit="ratio/month",
        source="data/calculated/metrics.csv",
        operation="subtract_nan",
        empty_division_result=math.nan,
    ),
    "fi_ratio_12m": FormulaSpec(
        id="fi_ratio_12m",
        label="FI比率（12か月）",
        formula="investment_gain_loss_12m / expenditure_12m",
        inputs=("investment_gain_loss_12m", "expenditure_12m"),
        unit="ratio",
        source="data/calculated/metrics.csv + data/calculated/balance_sheet.csv + data/calculated/cashflow.csv",
        operation="divide",
    ),
    "fi_ratio_48m": FormulaSpec(
        id="fi_ratio_48m",
        label="FI比率（48か月）",
        formula="investment_gain_loss_48m / expenditure_48m",
        inputs=("investment_gain_loss_48m", "expenditure_48m"),
        unit="ratio",
        source="data/calculated/metrics.csv + data/calculated/balance_sheet.csv + data/calculated/cashflow.csv",
        operation="divide",
    ),
    "fi_ratio_next_12m": FormulaSpec(
        id="fi_ratio_next_12m",
        label="予測FI比率（12か月）",
        formula="risk_and_pension_assets * expected_annual_return / expenditure_12m",
        inputs=(
            "risk_and_pension_assets",
            "expected_annual_return",
            "expenditure_12m",
        ),
        unit="ratio",
        source="data/calculated/metrics.csv + src/constants.py",
        operation="multiply_divide",
    ),
}


def _values(spec: FormulaSpec, values: Mapping[str, float]) -> list[float]:
    missing = [name for name in spec.inputs if name not in values]
    if missing:
        raise KeyError(f"{spec.id}: missing inputs: {', '.join(missing)}")
    return [float(values[name]) for name in spec.inputs]


def evaluate_formula(formula_id: str, values: Mapping[str, float]) -> float:
    spec = FORMULA_MANIFEST[formula_id]
    operands = _values(spec, values)

    if spec.operation == "sum":
        return sum(operands)
    if spec.operation in {"subtract", "subtract_nan"}:
        if spec.operation == "subtract_nan" and not all(math.isfinite(v) for v in operands):
            return math.nan
        return operands[0] - sum(operands[1:])
    if spec.operation in {"divide", "divide_nan"}:
        numerator, denominator = operands
        if denominator == 0 or not math.isfinite(denominator):
            return spec.empty_division_result
        return numerator / denominator
    if spec.operation == "multiply_divide":
        *numerators, denominator = operands
        if denominator == 0 or not math.isfinite(denominator):
            return spec.empty_division_result
        return reduce(mul, numerators, 1.0) / denominator
    raise ValueError(f"Unsupported formula operation: {spec.operation}")


def trace_formula(
    formula_id: str,
    values: Mapping[str, float],
    *,
    digits: int | None = None,
) -> CalculationTrace:
    spec = FORMULA_MANIFEST[formula_id]
    normalized = {name: float(values[name]) for name in spec.inputs}
    raw = evaluate_formula(formula_id, normalized)
    rounded: float | int
    if not math.isfinite(raw):
        rounded = raw
    elif digits is None:
        rounded = round(raw)
    else:
        rounded = round(raw, digits)
    return CalculationTrace(spec, normalized, raw, rounded)


def manifest_rows() -> Sequence[FormulaSpec]:
    return tuple(FORMULA_MANIFEST.values())
