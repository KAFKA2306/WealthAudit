"""Generate a JPY-consistent 30-year forecast and raw-return audit fields."""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from src.constants import (
    BENCHMARK_EXPECTED_ANNUAL_RETURN,
    FIXED_EXPENSE_CV_THRESHOLD,
    PORTFOLIO_EXPECTED_ANNUAL_RETURN,
)
from src.use_cases.valuation import previous_month

FORECAST_MONTHS = 360
RAISE_MONTH = 4


def annual_to_monthly_rate(annual_rate: float) -> float:
    if annual_rate <= -1:
        raise ValueError("annual_rate must be greater than -1")
    return (1 + annual_rate) ** (1 / 12) - 1


def calculate_cv(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return 0.0 if values.empty or values.mean() == 0 else float(values.std() / abs(values.mean()))


def geometric_mean_return(returns: Iterable[float]) -> float:
    values = [float(value) for value in returns if pd.notna(value)]
    values = [value for value in values if math.isfinite(value) and value > -1]
    return math.nan if not values else float(np.prod(np.array(values) + 1) ** (1 / len(values)) - 1)


def get_bonus_months() -> list[int]:
    return [6, 12]


def is_bonus_month(month: int) -> bool:
    return month in get_bonus_months()


def account_name_by_id(accounts: pd.DataFrame) -> dict[str, str]:
    return dict(zip(accounts["account_id"].astype(str), accounts["name"].astype(str)))


def income_col(account_id: str, account_names: dict[str, str]) -> str | None:
    name = account_names.get(str(account_id))
    return f"収入_{name}" if name else None


def parse_account_ids(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def forecast_fixed_income(
    history: pd.DataFrame, col: str, future_months: list[str]
) -> dict[str, float]:
    values = pd.to_numeric(history[col], errors="coerce").dropna()
    last_value = float(values.iloc[-1]) if not values.empty else 0.0
    return dict.fromkeys(future_months, last_value)


def forecast_other_income(
    history: pd.DataFrame, col: str, future_months: list[str]
) -> dict[str, float]:
    values = pd.to_numeric(history[col], errors="coerce").dropna().tail(3)
    average = float(values.mean()) if not values.empty else 0.0
    return dict.fromkeys(future_months, average)


def forecast_minna_income(
    history: pd.DataFrame,
    col: str,
    future_months: list[str],
    stats: list[dict[str, object]] | None = None,
) -> dict[str, float]:
    values = pd.to_numeric(history[col], errors="coerce").fillna(0.0).to_numpy()
    decrease_rates = [
        (values[index - 1] - values[index]) / values[index - 1]
        for index in range(1, len(values))
        if values[index - 1] > 0 and values[index] < values[index - 1]
    ]
    decrease = float(np.mean(decrease_rates)) if decrease_rates else 0.5
    previous = float(values[-1]) if len(values) else 0.0
    result: dict[str, float] = {}
    for month in future_months:
        previous = max(0.0, previous * (1 - decrease))
        result[month] = previous
    if stats is not None:
        stats.append(
            {
                "category": "Income",
                "item": col,
                "parameter": "decrease_rate",
                "value": decrease,
            }
        )
    return result


def forecast_stream_amount(
    history: pd.DataFrame,
    stream: pd.Series,
    account_names: dict[str, str],
    future_months: list[str],
    stats: list[dict[str, object]] | None = None,
) -> dict[str, float]:
    source_columns = [
        column
        for account_id in parse_account_ids(str(stream["source_account_ids"]))
        if (column := income_col(account_id, account_names)) in history.columns
    ]
    stream_column = f"stream_{stream['stream_id']}"
    stream_history = history[["month"]].copy()
    stream_history[stream_column] = (
        history[source_columns].sum(axis=1) if source_columns else 0.0
    )
    kind = str(stream["kind"])
    if kind == "cash_income":
        return forecast_salary_income(
            stream_history, stream_column, future_months, stats
        )
    if kind == "drawdown":
        return forecast_minna_income(
            stream_history, stream_column, future_months, stats
        )
    if kind == "asset_contribution":
        return forecast_fixed_income(
            stream_history, stream_column, future_months
        )
    return forecast_other_income(stream_history, stream_column, future_months)


def forecast_income_by_stream(
    history: pd.DataFrame,
    income_cols: list[str],
    future_months: list[str],
    accounts: pd.DataFrame,
    streams: pd.DataFrame,
    stats: list[dict[str, object]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    account_names = account_name_by_id(accounts)
    forecast_income = pd.DataFrame(
        0.0, index=future_months, columns=income_cols
    )
    stream_ids = streams["stream_id"].astype(str).tolist()
    stream_amounts = pd.DataFrame(
        0.0, index=future_months, columns=stream_ids
    )
    for _, stream in streams.iterrows():
        stream_id = str(stream["stream_id"])
        forecasts = forecast_stream_amount(
            history, stream, account_names, future_months, stats
        )
        stream_amounts[stream_id] = pd.Series(forecasts)
        destination = income_col(
            str(stream["forecast_to_account_id"]), account_names
        )
        if destination in forecast_income.columns:
            forecast_income[destination] += stream_amounts[stream_id]
    forecast_income.index.name = "month"
    stream_amounts.index.name = "month"
    return forecast_income, stream_amounts


def stream_kind_totals(
    stream_amounts: pd.DataFrame, streams: pd.DataFrame
) -> dict[str, pd.Series]:
    totals = {
        "cash_income": pd.Series(0.0, index=stream_amounts.index),
        "asset_contribution": pd.Series(
            0.0, index=stream_amounts.index
        ),
    }
    for _, stream in streams.iterrows():
        kind = str(stream["kind"])
        stream_id = str(stream["stream_id"])
        if kind in totals and stream_id in stream_amounts.columns:
            totals[kind] = totals[kind] + stream_amounts[stream_id]
    return totals


def _raise_boundaries(last_actual: pd.Timestamp, forecast_month: pd.Timestamp) -> int:
    return sum(
        last_actual < pd.Timestamp(year=year, month=RAISE_MONTH, day=1) <= forecast_month
        for year in range(last_actual.year, forecast_month.year + 1)
    )


def forecast_salary_income(
    history: pd.DataFrame,
    col: str,
    future_months: list[str],
    stats: list[dict[str, object]] | None = None,
) -> dict[str, float]:
    if not future_months:
        return {}
    frame = history[["month", col]].copy()
    frame["date"] = pd.to_datetime(frame["month"])
    frame["month_num"] = frame["date"].dt.month
    values = pd.to_numeric(frame[col], errors="coerce").fillna(0)
    if values.tail(6).sum() == 0:
        return dict.fromkeys(future_months, 0.0)
    regular = pd.to_numeric(
        frame.loc[~frame["month_num"].isin(get_bonus_months()), col], errors="coerce"
    )
    base = float(regular[regular > 0].tail(12).median())
    current_year = int(frame["date"].max().year)
    current = pd.to_numeric(
        frame.loc[(frame["date"].dt.year == current_year) & ~frame["month_num"].isin(get_bonus_months()), col],
        errors="coerce",
    )
    previous = pd.to_numeric(
        frame.loc[(frame["date"].dt.year == current_year - 1) & ~frame["month_num"].isin(get_bonus_months()), col],
        errors="coerce",
    )
    growth = float(current.mean() / previous.mean() - 1) if previous.mean() > 0 else 0.0
    growth = max(-0.95, min(growth, 1.0))
    last_actual = frame["date"].max()
    result: dict[str, float] = {}
    for month in future_months:
        date = pd.Timestamp(f"{month}-01")
        factor = (1 + growth) ** _raise_boundaries(last_actual, date)
        if is_bonus_month(date.month):
            bonus = pd.to_numeric(frame.loc[frame["month_num"] == date.month, col], errors="coerce")
            bonus = bonus[bonus > 0].tail(2)
            result[month] = (float(bonus.mean()) if not bonus.empty else base * 4) * factor
        else:
            result[month] = base * factor
    if stats is not None:
        stats.append({"category": "Income", "item": col, "parameter": "annual_growth", "value": growth})
    return result


def forecast_expense(
    history: pd.DataFrame,
    col: str,
    future_months: list[str],
    stats: list[dict[str, object]] | None = None,
) -> dict[str, float]:
    values = pd.to_numeric(history[col], errors="coerce").fillna(0)
    if "調整" in col:
        return dict.fromkeys(future_months, float(values.tail(3).median()))
    recent = float(values.tail(3).mean())
    prior = float(values.iloc[-15:-12].mean()) if len(values) >= 15 else recent
    trend = max(0.25, min(recent / prior if prior else 1.0, 4.0))
    if calculate_cv(values) < FIXED_EXPENSE_CV_THRESHOLD:
        result = dict.fromkeys(future_months, float(values.tail(12).mean()))
    else:
        frame = history[["month", col]].copy()
        frame["month_num"] = pd.to_datetime(frame["month"]).dt.month
        first_year = int(future_months[0][:4]) if future_months else 0
        result = {}
        for month in future_months:
            same_month = pd.to_numeric(
                frame.loc[frame["month_num"] == int(month[5:7]), col], errors="coerce"
            ).dropna()
            base = float(same_month.iloc[-1]) if not same_month.empty else recent
            result[month] = base * trend ** (int(month[:4]) - first_year + 1)
    if stats is not None:
        stats.append({"category": "Expense", "item": col, "parameter": "annual_trend", "value": trend})
    return result


def _consecutive_mask(months: pd.Series) -> pd.Series:
    prior = months.shift(1)
    return pd.Series(
        [False if pd.isna(before) else previous_month(str(current)) == str(before) for before, current in zip(prior, months)],
        index=months.index,
    )


def calculate_bs_derived(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["total_financial_assets"] = result[["liquid_assets", "risk_assets", "pension_assets"]].sum(axis=1)
    contiguous = _consecutive_mask(result["month"])
    contribution = result.get("net_worth_contribution", result.get("net_savings", 0.0))
    result["investment_gain_loss"] = np.where(
        contiguous,
        result["total_financial_assets"] - result["total_financial_assets"].shift(1) - contribution,
        0.0,
    )
    result["return_base_assets"] = np.where(
        contiguous, (result["risk_assets"] + result["pension_assets"]).shift(1), 0.0
    )
    return result


def _rolling_geometric(raw: pd.Series, months: pd.Series) -> pd.Series:
    values = {str(month): float(value) for month, value in zip(months, raw) if pd.notna(value)}
    result = []
    for month in months:
        date = pd.Timestamp(f"{month}-01")
        keys = [(date - pd.DateOffset(months=offset)).strftime("%Y-%m") for offset in range(12)]
        result.append(geometric_mean_return(values[key] for key in keys if key in values))
    return pd.Series(result, index=raw.index, dtype=float)


def calculate_metrics_vectorized(
    df: pd.DataFrame,
    portfolio_expected_monthly_return: float | None = None,
    benchmark_expected_monthly_return: float | None = None,
) -> pd.DataFrame:
    result = df.copy()
    denominator = pd.to_numeric(result["return_base_assets"], errors="coerce")
    raw = pd.Series(np.nan, index=result.index, dtype=float)
    raw.loc[denominator > 0] = result.loc[denominator > 0, "investment_gain_loss"] / denominator[denominator > 0]
    forecast_mask = result.get("is_forecast", pd.Series(False, index=result.index)).astype(bool)
    if portfolio_expected_monthly_return is not None:
        raw.loc[forecast_mask] = portfolio_expected_monthly_return
    result["raw_monthly_return"] = raw
    result["monthly_return"] = _rolling_geometric(raw, result["month"])

    benchmark = pd.to_numeric(result.get("raw_benchmark_return", pd.Series(np.nan, index=result.index)), errors="coerce")
    benchmark.loc[forecast_mask] = benchmark_expected_monthly_return if benchmark_expected_monthly_return is not None else np.nan
    result["raw_benchmark_return"] = benchmark
    result["benchmark_return"] = _rolling_geometric(benchmark, result["month"])
    result["monthly_alpha"] = result["monthly_return"] - result["benchmark_return"]
    if benchmark_expected_monthly_return is None:
        result.loc[forecast_mask, ["benchmark_return", "monthly_alpha"]] = np.nan

    income = result["after_tax_income"].rolling(12, min_periods=1).sum()
    savings = result["net_savings"].rolling(12, min_periods=1).sum()
    expense = result["expenditure"].rolling(12, min_periods=1).sum()
    gain = result["investment_gain_loss"].rolling(12, min_periods=1).sum()
    result["savings_rate"] = np.where(income != 0, savings / income, 0.0)
    result["risk_asset_ratio"] = np.where(
        result["total_financial_assets"] != 0,
        (result["risk_assets"] + result["pension_assets"]) / result["total_financial_assets"],
        0.0,
    )
    result["fi_ratio_12m"] = np.where(expense != 0, gain / expense, 0.0)
    result["fi_ratio_48m"] = np.where(
        result["expenditure"].rolling(48, min_periods=1).sum() != 0,
        result["investment_gain_loss"].rolling(48, min_periods=1).sum() / result["expenditure"].rolling(48, min_periods=1).sum(),
        0.0,
    )
    result["fi_ratio_next_12m"] = np.where(
        expense != 0,
        (result["risk_assets"] + result["pension_assets"]) * PORTFOLIO_EXPECTED_ANNUAL_RETURN / expense,
        0.0,
    )
    return result


def export_annual_summary(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    frame = df.copy()
    frame["year"] = frame["month"].str[:4].astype(int)
    flow = [col for col in frame if col.startswith(("収入_", "支出_")) or col in {"after_tax_income", "expenditure", "net_savings", "asset_contribution", "net_worth_contribution", "investment_gain_loss"}]
    stock = [col for col in frame if col.startswith(("資産_", "分類_")) or col in {"liquid_assets", "risk_assets", "pension_assets", "total_financial_assets", "return_base_assets"}]
    grouped = frame.groupby("year", sort=True)
    annual = pd.concat([grouped[flow].sum(), grouped[stock].last()], axis=1)
    annual["annual_return"] = grouped["raw_monthly_return"].apply(lambda x: float(np.prod(1 + x.dropna()) - 1) if not x.dropna().empty else math.nan)
    annual["annual_benchmark_return"] = grouped["raw_benchmark_return"].apply(lambda x: float(np.prod(1 + x.dropna()) - 1) if not x.dropna().empty else math.nan)
    annual["annual_alpha"] = annual["annual_return"] - annual["annual_benchmark_return"]
    annual = annual.reset_index()
    output_dir.mkdir(parents=True, exist_ok=True)
    annual.to_csv(output_dir / "forecast_annual.csv", index=False)
    return annual


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    calculated = base / "data" / "calculated"
    history = pd.read_csv(calculated / "normalized.csv").sort_values("month").reset_index(drop=True)
    accounts = pd.read_csv(base / "master" / "accounts.csv")
    classes = pd.read_csv(base / "master" / "asset_classes.csv")
    history["is_forecast"] = False
    last = datetime.strptime(str(history["month"].max()), "%Y-%m")
    months = [(last + relativedelta(months=i)).strftime("%Y-%m") for i in range(1, FORECAST_MONTHS + 1)]
    forecast = pd.DataFrame({"month": months, "is_forecast": True})
    stats: list[dict[str, object]] = []
    income_cols = sorted(col for col in history if col.startswith("収入_"))
    expense_cols = sorted(col for col in history if col.startswith("支出_"))
    asset_cols = sorted(col for col in history if col.startswith("資産_"))
    class_cols = sorted(col for col in history if col.startswith("分類_"))
    for col in income_cols:
        forecast[col] = forecast["month"].map(forecast_salary_income(history, col, months, stats))
    for col in expense_cols:
        forecast[col] = forecast["month"].map(forecast_expense(history, col, months, stats))

    account_names = {str(row.account_id): str(row.name) for row in accounts.itertuples(index=False)}
    pension_ids = set(accounts.loc[accounts["type"] == "pension", "account_id"].astype(str))
    pension_income = [f"収入_{account_names[x]}" for x in pension_ids if f"収入_{account_names[x]}" in forecast]
    cash_income = [col for col in income_cols if col not in pension_income]
    forecast["cash_income"] = forecast[cash_income].sum(axis=1) / 10000
    forecast["asset_contribution"] = forecast[pension_income].sum(axis=1) / 10000
    forecast["expenditure"] = forecast[expense_cols].sum(axis=1) / 10000
    forecast["cash_savings"] = forecast["cash_income"] - forecast["expenditure"]
    forecast["net_worth_contribution"] = forecast["cash_savings"] + forecast["asset_contribution"]
    forecast["after_tax_income"] = forecast["cash_income"]
    forecast["net_savings"] = forecast["cash_savings"]

    observed = pd.to_numeric(history.get("raw_monthly_return", pd.Series(dtype=float)), errors="coerce").dropna().tail(60)
    portfolio_rate = geometric_mean_return(observed) if not observed.empty else annual_to_monthly_rate(PORTFOLIO_EXPECTED_ANNUAL_RETURN)
    if not math.isfinite(portfolio_rate):
        portfolio_rate = annual_to_monthly_rate(PORTFOLIO_EXPECTED_ANNUAL_RETURN)
    benchmark_rate = annual_to_monthly_rate(BENCHMARK_EXPECTED_ANNUAL_RETURN) if BENCHMARK_EXPECTED_ANNUAL_RETURN is not None else None

    account_asset = {str(row.account_id): f"資産_{row.name}" for row in accounts.itertuples(index=False)}
    pension_assets = [account_asset[x] for x in pension_ids if account_asset[x] in asset_cols]
    risk_assets = [account_asset[str(row.account_id)] for row in accounts.itertuples(index=False) if str(row.account_id) not in pension_ids and int(row.risk) == 1 and account_asset[str(row.account_id)] in asset_cols]
    liquid_assets = [col for col in asset_cols if col not in set(risk_assets + pension_assets)]
    class_risk = {str(row["name"]): int(row["risk_level"]) for _, row in classes.iterrows()}
    pension_classes = [col for col in class_cols if col == "分類_年金"]
    risk_classes = [col for col in class_cols if col not in pension_classes and class_risk.get(col.removeprefix("分類_"), 0) == 1]
    liquid_classes = [col for col in class_cols if col not in set(risk_classes + pension_classes)]
    account_balance = {col: float(history[col].iloc[-1]) for col in asset_cols}
    class_balance = {col: float(history[col].iloc[-1]) for col in class_cols}

    def distribute(columns: list[str], amount: float, balances: dict[str, float]) -> None:
        if columns and amount:
            target = max(columns, key=lambda col: balances.get(col, 0.0))
            balances[target] = balances.get(target, 0.0) + amount

    for index in forecast.index:
        for col in risk_assets + pension_assets:
            account_balance[col] *= 1 + portfolio_rate
        for col in risk_classes + pension_classes:
            class_balance[col] *= 1 + portfolio_rate
        contribution = float(forecast.loc[index, "asset_contribution"] * 10000)
        saving = float(forecast.loc[index, "cash_savings"] * 10000)
        distribute(pension_assets, contribution, account_balance)
        distribute(pension_classes, contribution, class_balance)
        distribute(risk_assets if saving >= 0 else liquid_assets, saving, account_balance)
        distribute(risk_classes if saving >= 0 else liquid_classes, saving, class_balance)
        for col in asset_cols:
            forecast.loc[index, col] = account_balance[col]
        for col in class_cols:
            forecast.loc[index, col] = class_balance[col]
        forecast.loc[index, "liquid_assets"] = sum(account_balance[col] for col in liquid_assets) / 10000
        forecast.loc[index, "risk_assets"] = sum(account_balance[col] for col in risk_assets) / 10000
        forecast.loc[index, "pension_assets"] = sum(account_balance[col] for col in pension_assets) / 10000

    for col, default in {"cash_income": history.get("after_tax_income", 0), "asset_contribution": 0.0, "cash_savings": history.get("net_savings", 0), "net_worth_contribution": history.get("net_savings", 0)}.items():
        if col not in history:
            history[col] = default
    combined = calculate_bs_derived(pd.concat([history, forecast], ignore_index=True, sort=False))
    combined = calculate_metrics_vectorized(combined, portfolio_rate, benchmark_rate)
    combined.to_csv(calculated / "forecast.csv", index=False)
    export_annual_summary(combined, calculated)
    pd.DataFrame(stats).to_csv(calculated / "forecast_parameters.csv", index=False)


if __name__ == "__main__":
    main()
