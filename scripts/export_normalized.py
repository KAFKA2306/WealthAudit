"""Export a single JPY-denominated normalized table.

Native balances remain available in ``asset_valuations.csv``. All ``資産_*`` and
``分類_*`` columns in ``normalized.csv`` are JPY values and are reconciled to the
balance-sheet totals.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.constants import AccountId, AccountType, AssetClassId, Currency
from src.domain.entities.models import Account, Asset, AssetClass, Market
from src.use_cases.valuation import value_assets


def _load_accounts(path: Path) -> list[Account]:
    frame = pd.read_csv(path)
    return [
        Account(
            id=AccountId(row["account_id"]),
            name=str(row["name"]),
            type=AccountType(row["type"]),
            currency=Currency(row["currency"]),
            risk=int(row["risk"]),
        )
        for _, row in frame.iterrows()
    ]


def _load_asset_classes(path: Path) -> list[AssetClass]:
    frame = pd.read_csv(path)
    return [
        AssetClass(
            id=AssetClassId(row["class_id"]),
            name=str(row["name"]),
            risk_level=int(row["risk_level"]),
        )
        for _, row in frame.iterrows()
    ]


def _row_currency(row: pd.Series) -> Currency | None:
    for column in ("native_currency", "currency"):
        if column in row.index and pd.notna(row[column]) and str(row[column]).strip():
            return Currency(str(row[column]).strip())
    return None


def _row_balance(row: pd.Series) -> float:
    for column in ("native_balance", "balance"):
        if column in row.index and pd.notna(row[column]):
            return float(row[column])
    raise ValueError("assets.csv requires native_balance or balance")


def _load_assets(path: Path) -> list[Asset]:
    frame = pd.read_csv(path)
    return [
        Asset(
            month=row["month"],
            account_id=AccountId(row["account_id"]),
            asset_class=AssetClassId(row["asset_class"]),
            native_balance=_row_balance(row),
            native_currency=_row_currency(row),
        )
        for _, row in frame.iterrows()
    ]


def _load_markets(path: Path) -> list[Market]:
    frame = pd.read_csv(path)
    return [
        Market(
            month=row["month"],
            usd_jpy=float(row["usd_jpy"]),
            eur_jpy=float(row["eur_jpy"]),
            sp500=float(row["sp500"]),
        )
        for _, row in frame.iterrows()
    ]


def _pivot(
    frame: pd.DataFrame,
    column: str,
    names: dict[str, str],
    prefix: str,
    required_ids: list[str],
) -> pd.DataFrame:
    result = frame.pivot_table(
        index="month",
        columns=column,
        values="jpy_value",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    for item_id in required_ids:
        if item_id not in result.columns:
            result[item_id] = 0.0
    renamed = ["month"] + [
        f"{prefix}{names.get(str(item), str(item))}" for item in result.columns[1:]
    ]
    result.columns = renamed
    return result


def _validate_jpy_reconciliation(normalized: pd.DataFrame) -> None:
    asset_columns = [column for column in normalized if column.startswith("資産_")]
    class_columns = [column for column in normalized if column.startswith("分類_")]
    if "total_financial_assets" not in normalized:
        return

    for _, row in normalized.iterrows():
        if pd.isna(row.get("total_financial_assets")):
            continue
        expected = float(row["total_financial_assets"]) * 10000.0
        tolerance = max(2.0, abs(expected) * 1e-9)
        account_total = float(
            pd.to_numeric(row[asset_columns], errors="coerce").fillna(0.0).sum()
        )
        class_total = float(
            pd.to_numeric(row[class_columns], errors="coerce").fillna(0.0).sum()
        )
        if abs(account_total - expected) > tolerance:
            raise ValueError(
                f"JPY reconciliation failed for account assets in {row['month']}: "
                f"{account_total} != {expected}"
            )
        if abs(class_total - expected) > tolerance:
            raise ValueError(
                f"JPY reconciliation failed for asset classes in {row['month']}: "
                f"{class_total} != {expected}"
            )


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    input_dir = base_dir / "data" / "input"
    calculated_dir = base_dir / "data" / "calculated"
    master_dir = base_dir / "master"
    calculated_dir.mkdir(parents=True, exist_ok=True)

    accounts = _load_accounts(master_dir / "accounts.csv")
    asset_classes = _load_asset_classes(master_dir / "asset_classes.csv")
    assets = _load_assets(input_dir / "assets.csv")
    markets = _load_markets(input_dir / "market.csv")
    valuations = value_assets(assets, markets, accounts)

    valuation_frame = pd.DataFrame(
        [
            {
                "month": item.month,
                "account_id": item.account_id.value,
                "asset_class": item.asset_class.value,
                "native_currency": item.native_currency.value,
                "native_balance": item.native_balance,
                "fx_rate_to_jpy": item.fx_rate_to_jpy,
                "jpy_value": item.jpy_value,
            }
            for item in valuations
        ]
    )
    valuation_frame.to_csv(calculated_dir / "asset_valuations.csv", index=False)

    account_names = {item.id.value: item.name for item in accounts}
    class_names = {item.id.value: item.name for item in asset_classes}
    assets_by_account = _pivot(
        valuation_frame,
        "account_id",
        account_names,
        "資産_",
        list(account_names),
    )
    assets_by_class = _pivot(
        valuation_frame,
        "asset_class",
        class_names,
        "分類_",
        list(class_names),
    )

    income = pd.read_csv(input_dir / "income.csv")
    expense = pd.read_csv(input_dir / "expense.csv")
    payment_methods = pd.read_csv(master_dir / "payment_methods.csv")
    method_names = dict(
        zip(payment_methods["method_id"].astype(str), payment_methods["name"].astype(str))
    )

    income_by_account = income.pivot_table(
        index="month",
        columns="account_id",
        values="amount",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    for account_id in account_names:
        if account_id not in income_by_account.columns:
            income_by_account[account_id] = 0.0
    income_by_account.columns = ["month"] + [
        f"収入_{account_names.get(str(column), str(column))}"
        for column in income_by_account.columns[1:]
    ]

    expense_by_method = expense.pivot_table(
        index="month",
        columns="method_id",
        values="amount",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    for method_id in method_names:
        if method_id not in expense_by_method.columns:
            expense_by_method[method_id] = 0.0
    expense_by_method.columns = ["month"] + [
        f"支出_{method_names.get(str(column), str(column))}"
        for column in expense_by_method.columns[1:]
    ]

    normalized = income_by_account.merge(expense_by_method, on="month", how="outer")
    normalized = normalized.merge(
        pd.read_csv(calculated_dir / "cashflow.csv"), on="month", how="outer"
    )
    normalized = normalized.merge(assets_by_account, on="month", how="outer")
    normalized = normalized.merge(assets_by_class, on="month", how="outer")
    for filename in ("balance_sheet.csv", "metrics.csv"):
        normalized = normalized.merge(
            pd.read_csv(calculated_dir / filename), on="month", how="outer"
        )

    normalized = normalized.sort_values("month").reset_index(drop=True)
    ordered = ["month"]
    ordered += sorted(column for column in normalized if column.startswith("収入_"))
    ordered += sorted(column for column in normalized if column.startswith("支出_"))
    ordered += [
        column
        for column in (
            "after_tax_income",
            "expenditure",
            "net_savings",
            "asset_contribution",
            "net_worth_contribution",
        )
        if column in normalized
    ]
    ordered += sorted(column for column in normalized if column.startswith("資産_"))
    ordered += sorted(column for column in normalized if column.startswith("分類_"))
    ordered += [
        column
        for column in (
            "liquid_assets",
            "risk_assets",
            "pension_assets",
            "total_financial_assets",
            "investment_gain_loss",
            "return_base_assets",
            "savings_rate",
            "risk_asset_ratio",
            "raw_monthly_return",
            "monthly_return",
            "raw_benchmark_return",
            "benchmark_return",
            "monthly_alpha",
            "fi_ratio_12m",
            "fi_ratio_48m",
            "fi_ratio_next_12m",
        )
        if column in normalized
    ]
    ordered += [column for column in normalized if column not in ordered]
    normalized = normalized[ordered]

    _validate_jpy_reconciliation(normalized)
    normalized.to_csv(calculated_dir / "normalized.csv", index=False)
    print(
        "Exported normalized.csv with JPY-denominated asset columns and "
        "asset_valuations.csv with native units"
    )


if __name__ == "__main__":
    main()
