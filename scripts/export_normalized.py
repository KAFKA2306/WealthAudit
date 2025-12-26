"""
Export normalized table by joining all input and calculated CSVs.

Combines:
- data/input: assets.csv, income.csv, expense.csv (pivoted by master patterns)
- data/calculated: balance_sheet.csv, cashflow.csv, metrics.csv
- master: accounts.csv, asset_classes.csv, payment_methods.csv

All tables are joined on 'month' as the primary key.
Columns are expanded based on master CSV patterns.
"""

import pandas as pd
from pathlib import Path


def main() -> None:
    """Join all input and calculated CSVs and export as a normalized table."""
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    input_dir = data_dir / "input"
    calculated_dir = data_dir / "calculated"
    master_dir = base_dir / "master"
    output_path = calculated_dir / "normalized.csv"

    # Load master files
    accounts = pd.read_csv(master_dir / "accounts.csv")
    asset_classes = pd.read_csv(master_dir / "asset_classes.csv")
    payment_methods = pd.read_csv(master_dir / "payment_methods.csv")

    # Create ID to name mappings
    account_names = dict(zip(accounts["account_id"], accounts["name"]))
    class_names = dict(zip(asset_classes["class_id"], asset_classes["name"]))
    method_names = dict(zip(payment_methods["method_id"], payment_methods["name"]))

    # Load input CSVs
    assets = pd.read_csv(input_dir / "assets.csv")
    income = pd.read_csv(input_dir / "income.csv")
    expense = pd.read_csv(input_dir / "expense.csv")

    # Pivot assets by account_id (balance per account)
    assets_by_account = assets.pivot_table(
        index="month",
        columns="account_id",
        values="balance",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    # Ensure all accounts exist
    for acc_id in accounts["account_id"]:
        if acc_id not in assets_by_account.columns:
            assets_by_account[acc_id] = 0
    assets_by_account.columns = ["month"] + [
        f"資産_{account_names.get(col, col)}" for col in assets_by_account.columns[1:]
    ]

    # Pivot assets by asset_class (balance per asset class)
    assets_by_class = assets.pivot_table(
        index="month",
        columns="asset_class",
        values="balance",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    # Ensure all asset classes exist
    for class_id in asset_classes["class_id"]:
        if class_id not in assets_by_class.columns:
            assets_by_class[class_id] = 0
    assets_by_class.columns = ["month"] + [
        f"分類_{class_names.get(col, col)}" for col in assets_by_class.columns[1:]
    ]

    # Pivot income by account_id
    income_by_account = income.pivot_table(
        index="month",
        columns="account_id",
        values="amount",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    # Ensure all accounts exist (for income)
    for acc_id in accounts["account_id"]:
        if acc_id not in income_by_account.columns:
            income_by_account[acc_id] = 0
    income_by_account.columns = ["month"] + [
        f"収入_{account_names.get(col, col)}" for col in income_by_account.columns[1:]
    ]

    # Pivot expense by method_id
    expense_by_method = expense.pivot_table(
        index="month",
        columns="method_id",
        values="amount",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    # Ensure all payment methods exist
    for method_id in payment_methods["method_id"]:
        if method_id not in expense_by_method.columns:
            expense_by_method[method_id] = 0
    expense_by_method.columns = ["month"] + [
        f"支出_{method_names.get(col, col)}" for col in expense_by_method.columns[1:]
    ]

    # Load all calculated CSVs
    balance_sheet = pd.read_csv(calculated_dir / "balance_sheet.csv")
    cashflow = pd.read_csv(calculated_dir / "cashflow.csv")
    metrics = pd.read_csv(calculated_dir / "metrics.csv")

    # Join all tables on 'month' column
    # Order: P/L (income → expense) → B/S (class → account) → calculated metrics
    normalized = income_by_account.merge(expense_by_method, on="month", how="outer")
    normalized = normalized.merge(cashflow, on="month", how="outer")
    normalized = normalized.merge(assets_by_class, on="month", how="outer")
    normalized = normalized.merge(assets_by_account, on="month", how="outer")
    normalized = normalized.merge(balance_sheet, on="month", how="outer")
    normalized = normalized.merge(metrics, on="month", how="outer")

    # Sort by month
    normalized = normalized.sort_values("month").reset_index(drop=True)

    # Define column order based on finance logic
    # 1. month (primary key)
    # 2. P/L: 収入 (income) → 支出 (expense) → net savings
    # 3. B/S: 分類 (asset class) → 資産 (by account) → balance sheet totals
    # 4. Metrics: ratios and returns
    col_order = ["month"]
    income_cols = sorted([c for c in normalized.columns if c.startswith("収入_")])
    expense_cols = sorted([c for c in normalized.columns if c.startswith("支出_")])
    cashflow_cols = ["after_tax_income", "expenditure", "net_savings"]
    class_cols = sorted([c for c in normalized.columns if c.startswith("分類_")])
    asset_cols = sorted([c for c in normalized.columns if c.startswith("資産_")])
    bs_cols = ["liquid_assets", "risk_assets", "pension_assets", "total_financial_assets", "investment_gain_loss"]
    metric_cols = ["savings_rate", "risk_asset_ratio", "monthly_return", "monthly_alpha", 
                   "benchmark_return", "fi_ratio_12m", "fi_ratio_48m", "fi_ratio_next_12m"]
    
    # Filter to only include columns that exist
    all_ordered = col_order + income_cols + expense_cols
    all_ordered += [c for c in cashflow_cols if c in normalized.columns]
    # Swap: 資産 (Asset Account) first, then 分類 (Asset Class)
    all_ordered += asset_cols + class_cols
    all_ordered += [c for c in bs_cols if c in normalized.columns]
    all_ordered += [c for c in metric_cols if c in normalized.columns]
    
    # Add any remaining columns not in the order
    remaining = [c for c in normalized.columns if c not in all_ordered]
    all_ordered += remaining
    
    normalized = normalized[all_ordered]

    # Round numeric columns to 4 significant figures
    numeric_cols = normalized.select_dtypes(include=["float64", "int64"]).columns
    for col in numeric_cols:
        normalized[col] = normalized[col].apply(
            lambda x: float(f"{x:.4g}") if pd.notna(x) else x
        )

    # Export to CSV
    normalized.to_csv(output_path, index=False)
    print(f"Exported normalized table to: {output_path}")
    print(f"Rows: {len(normalized)}, Columns: {len(normalized.columns)}")
    print(f"\nColumn order (finance logic):")
    print(f"  1. month")
    print(f"  2. P/L: 収入_* → 支出_* → cashflow")
    print(f"  3. B/S: 資産_* (Account) → 分類_* (Class) → balance_sheet")
    print(f"  4. Metrics: ratios, returns")


if __name__ == "__main__":
    main()
