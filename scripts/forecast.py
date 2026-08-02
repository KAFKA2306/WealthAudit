"""
Forecast future 12 months of financial data.

Based on logic documented in docs/logics/forecast.md.
Generates data/calculated/forecast.csv with predicted values.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from src.constants import EXPECTED_ANNUAL_RETURN, FIXED_EXPENSE_CV_THRESHOLD
from src.utils.months import month_end_label, month_period


def calculate_cv(series: pd.Series) -> float:
    """Calculate coefficient of variation."""
    mean = series.mean()
    if mean == 0:
        return 0
    return series.std() / abs(mean)


def geometric_mean_return(returns: pd.Series) -> float:
    """Calculate geometric mean of returns."""
    valid_returns = returns.dropna()
    if len(valid_returns) == 0:
        return 0
    product = np.prod(1 + valid_returns)
    return product ** (1 / len(valid_returns)) - 1


def get_bonus_months() -> list[int]:
    """Return bonus months (June and December)."""
    return [6, 12]


def is_bonus_month(month: int) -> bool:
    """Check if month is a bonus month."""
    return month in get_bonus_months()


def load_accounts(base_dir: Path) -> pd.DataFrame:
    return pd.read_csv(base_dir / "master" / "accounts.csv")


def load_forecast_streams(base_dir: Path) -> pd.DataFrame:
    required_cols = {
        "stream_id",
        "display_name",
        "kind",
        "source_account_ids",
        "forecast_to_account_id",
    }
    streams = pd.read_csv(base_dir / "master" / "forecast_streams.csv").fillna("")
    missing = required_cols - set(streams.columns)
    if missing:
        raise ValueError(f"forecast_streams.csv missing columns: {sorted(missing)}")
    return streams


def account_name_by_id(accounts: pd.DataFrame) -> dict[str, str]:
    return dict(zip(accounts["account_id"], accounts["name"]))


def income_col(account_id: str, account_names: dict[str, str]) -> str | None:
    name = account_names.get(account_id)
    return f"収入_{name}" if name else None


def asset_col(account_id: str, account_names: dict[str, str]) -> str | None:
    name = account_names.get(account_id)
    return f"資産_{name}" if name else None


def parse_account_ids(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def forecast_stream_amount(
    history: pd.DataFrame,
    stream: pd.Series,
    account_names: dict[str, str],
    future_months: list[str],
    stats: list | None = None,
) -> dict[str, float]:
    source_cols = [
        col
        for account_id in parse_account_ids(stream["source_account_ids"])
        if (col := income_col(account_id, account_names)) in history.columns
    ]
    stream_col = f"stream_{stream['stream_id']}"
    stream_history = history[["month"]].copy()
    stream_history[stream_col] = (
        history[source_cols].sum(axis=1) if source_cols else 0.0
    )

    kind = stream["kind"]
    if kind == "cash_income":
        return forecast_salary_income(stream_history, stream_col, future_months, stats)
    if kind == "drawdown":
        return forecast_minna_income(stream_history, stream_col, future_months, stats)
    if kind == "asset_contribution":
        return forecast_fixed_income(stream_history, stream_col, future_months)
    if kind == "transfer_like":
        return forecast_other_income(stream_history, stream_col, future_months)

    return forecast_other_income(stream_history, stream_col, future_months)


def forecast_income_by_stream(
    history: pd.DataFrame,
    income_cols: list[str],
    future_months: list[str],
    accounts: pd.DataFrame,
    streams: pd.DataFrame,
    stats: list | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    account_names = account_name_by_id(accounts)
    forecast_income = pd.DataFrame(0.0, index=future_months, columns=income_cols)
    stream_amounts = pd.DataFrame(0.0, index=future_months, columns=streams["stream_id"])

    for _, stream in streams.iterrows():
        forecasts = forecast_stream_amount(
            history, stream, account_names, future_months, stats
        )
        stream_id = stream["stream_id"]
        stream_amounts[stream_id] = pd.Series(forecasts)

        destination = income_col(stream["forecast_to_account_id"], account_names)
        if destination in forecast_income.columns:
            forecast_income[destination] += stream_amounts[stream_id]

    forecast_income.index.name = "month"
    stream_amounts.index.name = "month"
    return forecast_income, stream_amounts


def stream_kind_totals(stream_amounts: pd.DataFrame, streams: pd.DataFrame) -> dict[str, pd.Series]:
    totals = {
        "cash_income": pd.Series(0.0, index=stream_amounts.index),
        "asset_contribution": pd.Series(0.0, index=stream_amounts.index),
    }
    for _, stream in streams.iterrows():
        kind = stream["kind"]
        if kind in totals and stream["stream_id"] in stream_amounts.columns:
            totals[kind] = totals[kind] + stream_amounts[stream["stream_id"]]
    return totals


def classify_asset_columns(
    asset_cols: list[str], accounts: pd.DataFrame
) -> tuple[list[str], list[str], list[str]]:
    account_names = account_name_by_id(accounts)
    cash_accounts: list[str] = []
    risk_accounts: list[str] = []
    pension_accounts: list[str] = []

    for _, account in accounts.iterrows():
        col = asset_col(account["account_id"], account_names)
        if col not in asset_cols:
            continue

        account_type = account["type"]
        is_risk = int(account["risk"]) == 1
        if account_type == "pension":
            pension_accounts.append(col)
        elif is_risk:
            risk_accounts.append(col)
        else:
            cash_accounts.append(col)

    return cash_accounts, risk_accounts, pension_accounts


def contribution_columns_by_asset(
    streams: pd.DataFrame, account_names: dict[str, str]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for _, stream in streams[streams["kind"] == "asset_contribution"].iterrows():
        income = income_col(stream["forecast_to_account_id"], account_names)
        asset = asset_col(stream["forecast_to_account_id"], account_names)
        if income and asset:
            result[asset] = income
    return result


def preferred_cash_asset_column(
    streams: pd.DataFrame, account_names: dict[str, str], cash_accounts: list[str]
) -> str | None:
    for _, stream in streams[streams["kind"] == "cash_income"].iterrows():
        destination = asset_col(stream["forecast_to_account_id"], account_names)
        if destination in cash_accounts:
            return destination
    return cash_accounts[0] if cash_accounts else None


def forecast_salary_income(
    history: pd.DataFrame, col: str, future_months: list[str], stats: list = None
) -> dict[str, float]:
    """Forecast salary income with annual raise logic, using recent data."""
    bonus_months = get_bonus_months()
    
    # Check if this account is actively used (recent 6 months)
    recent_values = history[col].tail(6)
    if recent_values.sum() == 0:
        # Account not used recently - return 0
        return {month: 0 for month in future_months}
    
    # Get regular months (non-bonus) from recent data
    history = history.copy()
    history["month_num"] = pd.to_datetime(history["month"]).dt.month
    regular_mask = ~history["month_num"].isin(bonus_months)
    
    # Use recent 12 months for base calculation
    recent_history = history.tail(12)
    recent_regular = recent_history.loc[recent_history["month_num"].isin(
        [m for m in range(1, 13) if m not in bonus_months]
    ), col]
    
    # Calculate annual growth rate from year-over-year comparison
    current_year = pd.to_datetime(history["month"].max()).year
    current_year_mask = pd.to_datetime(history["month"]).dt.year == current_year
    prev_year_mask = pd.to_datetime(history["month"]).dt.year == current_year - 1
    
    current_regular_avg = history.loc[regular_mask & current_year_mask, col].mean()
    prev_regular_avg = history.loc[regular_mask & prev_year_mask, col].mean()
    
    if prev_regular_avg > 0 and not np.isnan(current_regular_avg) and not np.isnan(prev_regular_avg):
        annual_growth = (current_regular_avg / prev_regular_avg) - 1
    else:
        annual_growth = 0
    
    # Use recent 6-month median for regular months (excluding bonus months and zeros)
    recent_regular_nonzero = recent_regular[recent_regular > 0]
    if len(recent_regular_nonzero) > 0:
        regular_base = recent_regular_nonzero.median()
    else:
        regular_base = recent_values[recent_values > 0].median()
        if np.isnan(regular_base):
            regular_base = 0
    
    forecasts = {}
    base_year = int(future_months[0].split("-")[0])
    
    for month_str in future_months:
        year = int(month_str.split("-")[0])
        month_num = int(month_str.split("-")[1])
        years_ahead = year - base_year  # Compound growth for each year
        growth_factor = (1 + annual_growth) ** (years_ahead + 1)
        
        if is_bonus_month(month_num):
            # Use recent bonus month values
            same_month_mask = history["month_num"] == month_num
            recent_bonus = history.loc[same_month_mask, col].tail(2)
            bonus_avg = recent_bonus[recent_bonus > 0].mean()
            if np.isnan(bonus_avg) or bonus_avg == 0:
                bonus_avg = regular_base * 4  # Estimate if no history
            forecasts[month_str] = bonus_avg * growth_factor
        else:
            forecasts[month_str] = regular_base * growth_factor
    
    if stats is not None:
        stats.append({
            "category": "Income",
            "item": col,
            "parameter": "active",
            "value": 1,
            "unit": "boolean",
            "description": "Account is active (recent income > 0)"
        })
        stats.append({
            "category": "Income",
            "item": col,
            "parameter": "annual_growth",
            "value": float(f"{annual_growth:.4f}"),
            "unit": "rate",
            "description": "Annual growth rate based on year-over-year regular income"
        })
        stats.append({
            "category": "Income",
            "item": col,
            "parameter": "regular_base",
            "value": int(regular_base),
            "unit": "JPY",
            "description": "Base monthly income (median of recent regular months)"
        })
        stats.append({
            "category": "Income",
            "item": col,
            "parameter": "bonus_avg",
            "value": int(bonus_avg if 'bonus_avg' in locals() else 0),
            "unit": "JPY",
            "description": "Average bonus amount"
        })

    return forecasts


def forecast_minna_income(
    history: pd.DataFrame, col: str, future_months: list[str], stats: list = None
) -> dict[str, float]:
    """Forecast Minna Bank income with monotonic decrease."""
    values = history[col].values
    
    # Calculate average monthly decrease rate
    decrease_rates = []
    for i in range(1, len(values)):
        if values[i-1] > 0:
            rate = (values[i-1] - values[i]) / values[i-1]
            if rate > 0:  # Only positive decrease
                decrease_rates.append(rate)
    
    avg_decrease = np.mean(decrease_rates) if decrease_rates else 0.5
    
    forecasts = {}
    prev_value = values[-1] if len(values) > 0 else 0
    
    for month_str in future_months:
        new_value = max(0, prev_value * (1 - avg_decrease))
        forecasts[month_str] = new_value
        prev_value = new_value
    
    return forecasts

    if stats is not None:
        stats.append({
            "category": "Income",
            "item": col,
            "parameter": "decrease_rate",
            "value": float(f"{avg_decrease:.4f}"),
            "unit": "rate",
            "description": "Average monthly decrease rate"
        })


def forecast_fixed_income(
    history: pd.DataFrame, col: str, future_months: list[str]
) -> dict[str, float]:
    """Forecast fixed income (pension, DC) using last value."""
    last_value = history[col].iloc[-1] if len(history) > 0 else 0
    return {month: last_value for month in future_months}


def forecast_other_income(
    history: pd.DataFrame, col: str, future_months: list[str]
) -> dict[str, float]:
    """Forecast other income using 3-month average."""
    avg = history[col].tail(3).mean()
    if np.isnan(avg):
        avg = 0
    return {month: avg for month in future_months}


def forecast_expense(
    history: pd.DataFrame, col: str, future_months: list[str], stats: list = None
) -> dict[str, float]:
    """Forecast expense using trend adjustment method."""
    history = history.copy()
    values = history[col]
    cv = calculate_cv(values)
    
    # Special handling for adjustment column (調整) - use 3-month median
    if "調整" in col:
        median = values.tail(3).median()
        return {month: median if not np.isnan(median) else 0 for month in future_months}
    
    # Recent 3-month average
    recent_avg = values.tail(3).mean()
    if np.isnan(recent_avg):
        recent_avg = 0
    
    # Same-period-last-year 3-month average (for trend ratio)
    if len(values) >= 15:
        same_period_last_year_avg = values.iloc[-15:-12].mean()
    else:
        same_period_last_year_avg = recent_avg
    if np.isnan(same_period_last_year_avg) or same_period_last_year_avg == 0:
        same_period_last_year_avg = recent_avg if recent_avg != 0 else 1
    
    # Trend ratio: how spending changed year-over-year
    trend_ratio = recent_avg / same_period_last_year_avg if same_period_last_year_avg != 0 else 1
    
    forecasts = {}
    if cv < FIXED_EXPENSE_CV_THRESHOLD:
        # Fixed expense: 12-month average
        avg = values.tail(12).mean()
        for month_str in future_months:
            forecasts[month_str] = avg if not np.isnan(avg) else 0
    else:
        # Variable expense: 12-month-ago value × trend ratio
        history["month_num"] = pd.to_datetime(history["month"]).dt.month
        for month_str in future_months:
            month_num = int(month_str.split("-")[1])
            same_month = history[history["month_num"] == month_num][col]
            if len(same_month) > 0:
                same_month_val = same_month.iloc[-1]
                # Apply trend adjustment
                forecasts[month_str] = same_month_val * trend_ratio
            else:
                forecasts[month_str] = recent_avg * trend_ratio


    if stats is not None:
        stats.append({
            "category": "Expense",
            "item": col,
            "parameter": "cv",
            "value": float(f"{cv:.4f}"),
            "unit": "ratio",
            "description": "Coefficient of Variation (std/mean)"
        })
        is_fixed = cv < FIXED_EXPENSE_CV_THRESHOLD
        stats.append({
            "category": "Expense",
            "item": col,
            "parameter": "type",
            "value": "Fixed" if is_fixed else "Variable",
            "unit": "type",
            "description": "Expense type classification"
        })
        if not is_fixed:
            stats.append({
                "category": "Expense",
                "item": col,
                "parameter": "trend_ratio",
                "value": float(f"{trend_ratio:.4f}"),
                "unit": "ratio",
                "description": "Trend ratio (Recent 3m / Last Year 3m)"
            })
    
    return forecasts



def calculate_bs_derived(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate derived Balance Sheet items (Total Assets, Investment Gain/Loss).
    Ensures consistency across history and forecast.
    """
    # Recalculate Total Financial Assets to be sure
    df["total_financial_assets"] = (
        df["liquid_assets"] + 
        df["risk_assets"] + 
        df["pension_assets"]
    )
    
    # Investment Gain/Loss = Total(t) - Total(t-1) - Net Worth Contribution(t)
    prev_total = df["total_financial_assets"].shift(1)
    if "net_worth_contribution" in df.columns:
        contribution_col = "net_worth_contribution"
    elif "cash_savings" in df.columns and "asset_contribution" in df.columns:
        df["_derived_net_worth_contribution"] = (
            df["cash_savings"] + df["asset_contribution"]
        )
        contribution_col = "_derived_net_worth_contribution"
    elif "asset_contribution" in df.columns:
        df["_derived_net_worth_contribution"] = df["net_savings"] + df["asset_contribution"]
        contribution_col = "_derived_net_worth_contribution"
    else:
        contribution_col = "cash_savings" if "cash_savings" in df.columns else "net_savings"
    
    # Note: Shift(1) for the first item will be NaN, so Gain will be NaN.
    # For history start, this is acceptable (or 0).
    # For forecast start, it seamlessly uses history's last value.
    
    df["investment_gain_loss"] = (
        df["total_financial_assets"] - prev_total - df[contribution_col]
    )
    
    # Fill NaN for first row if needed (usually 0 or leave as NaN)
    df.loc[df["investment_gain_loss"].isna(), "investment_gain_loss"] = 0.0
    if "_derived_net_worth_contribution" in df.columns:
        df = df.drop(columns=["_derived_net_worth_contribution"])
    
    return df


def calculate_metrics_vectorized(df: pd.DataFrame, geo_return_rate: float) -> pd.DataFrame:
    """
    Calculate derived metrics on the combined dataframe using vectorized operations.
    Follows logic from src/use_cases/calculators/metrics.py.
    """
    # savings_rate: TTM Net Savings / TTM After Tax Income
    # Rolling 12 sums
    ttm_savings = df["net_savings"].rolling(window=12, min_periods=1).sum()
    ttm_income = df["after_tax_income"].rolling(window=12, min_periods=1).sum()
    df["savings_rate"] = 0.0
    mask = ttm_income != 0
    df.loc[mask, "savings_rate"] = ttm_savings[mask] / ttm_income[mask]
    
    # risk_asset_ratio: (Risk + Pension) / Total
    df["risk_asset_ratio"] = 0.0
    mask = df["total_financial_assets"] != 0
    df.loc[mask, "risk_asset_ratio"] = (
        df.loc[mask, "risk_assets"] + df.loc[mask, "pension_assets"]
    ) / df.loc[mask, "total_financial_assets"]
    
    # monthly_return: 12-month Geometric Mean of raw returns
    # Raw return = Investment Gain / Prev Month Risk Assets
    prev_risk = df["risk_assets"].shift(1)
    raw_return = pd.Series(0.0, index=df.index)
    mask = (prev_risk > 0) & (df["investment_gain_loss"].notna())
    raw_return[mask] = df.loc[mask, "investment_gain_loss"] / prev_risk[mask]
    
    # Geometric mean rolling 12
    # Product(1+r)^(1/n) - 1
    # Log approach: exp(mean(log(1+r))) - 1
    # Handle small negative returns safely (1+r > 0)
    log_returns = np.log1p(raw_return)
    roll_log_mean = log_returns.rolling(window=12, min_periods=1).mean()
    df["monthly_return"] = np.expm1(roll_log_mean)
    
    # benchmark_return: 12-month Geometric Mean
    # For history: we assume normalized.csv has 'benchmark_return' pre-calculated
    # For forecast: we assume it equals the assumed geo_return_rate constant
    # We need to fill forecast rows first
    # is_forecast = df["month"] > df["month"].iloc[len(df) - 360 - 1] # Approximate split
    # Better: identify which rows originally had NaN benchmark_return
    if "benchmark_return" not in df.columns:
        df["benchmark_return"] = 0.0
    
    # Fill forecast benchmark with constant expectation (to mimic market behavior)
    # But strictly, we should assume the 'market' returns this rate.
    # If normalized.csv already has TTM benchmark return, we might break it by overwriting.
    # Ideally, we reconstruction 'raw' benchmark return for history if possible, or carry forward.
    # Given we don't have S&P500 index in normalized.csv, we will perform a simplified approach:
    # Use existing benchmark_return for history, and for forecast use the constant rate.
    # Note: metrics.py calculates TTM geom mean.
    # Let's assume for forecast, the raw benchmark return is 'geo_return_rate'.
    # So the TTM geom mean will converge to 'geo_return_rate'.
    # We will just fill the column for forecast with the constant.
    # forecast_mask = df["benchmark_return"].isna() | (df["benchmark_return"] == 0) # Simplification
    # Correct way: Identify forecast rows by index or month
    # We know forecast is appended at end.
    # Actually, normalized.csv has 'benchmark_return' which is ALREADY the TTM value from metrics.py?
    # No, metrics.csv has TTM values. normalized.csv merges metrics.csv.
    # So history rows already have the correct TTM value.
    # We only need to calculate for Forecast rows.
    # For forecast rows, if we assume constant return, the TTM average is that constant.
    # So we can just set it.
    df.loc[df["benchmark_return"].isna(), "benchmark_return"] = geo_return_rate
    
    # monthly_alpha
    df["monthly_alpha"] = df["monthly_return"] - df["benchmark_return"]
    
    # FI Ratios
    # fi_ratio_12m: TTM Gain / TTM Expense
    ttm_gain = df["investment_gain_loss"].rolling(window=12, min_periods=1).sum()
    ttm_expense = df["expenditure"].rolling(window=12, min_periods=1).sum()
    
    df["fi_ratio_12m"] = 0.0
    mask = ttm_expense != 0
    df.loc[mask, "fi_ratio_12m"] = ttm_gain[mask] / ttm_expense[mask]
    
    # fi_ratio_48m: 48m Gain / 48m Expense
    gain_48 = df["investment_gain_loss"].rolling(window=48, min_periods=1).sum()
    expense_48 = df["expenditure"].rolling(window=48, min_periods=1).sum()
    
    df["fi_ratio_48m"] = 0.0
    mask = expense_48 != 0
    df.loc[mask, "fi_ratio_48m"] = gain_48[mask] / expense_48[mask]
    
    # fi_ratio_next_12m: (Risk * EXPECTED_ANNUAL_RETURN) / TTM Expense
    df["fi_ratio_next_12m"] = 0.0
    mask = ttm_expense != 0
    df.loc[mask, "fi_ratio_next_12m"] = (df.loc[mask, "risk_assets"] * EXPECTED_ANNUAL_RETURN) / ttm_expense[mask]
    
    return df


def get_calendar_year(month_str: str) -> int:
    """Get calendar year from a month-end label."""
    return int(month_str.split("-")[0])


def export_annual_summary(df: pd.DataFrame, output_dir: Path) -> None:
    """
    Aggregate forecast data by Calendar Year and export summary.
    Calendar Year: January to December.
    Flows: Sum
    Stocks: Last value
    Metrics: Recalculated
    """
    df = df.copy().sort_values("month").reset_index(drop=True)
    df["year"] = df["month"].apply(get_calendar_year)
    prev_risk_assets = df["risk_assets"].shift(1)
    df["raw_monthly_return"] = 0.0
    raw_mask = prev_risk_assets > 0
    df.loc[raw_mask, "raw_monthly_return"] = (
        df.loc[raw_mask, "investment_gain_loss"] / prev_risk_assets[raw_mask]
    )
    
    # Define aggregation rules
    # 1. Flows (Sum)
    inc_cols = [c for c in df.columns if c.startswith("収入_")]
    exp_cols = [c for c in df.columns if c.startswith("支出_")]
    derived_flow_cols = [
        "cash_income",
        "asset_contribution",
        "cash_savings",
        "net_worth_contribution",
        "after_tax_income",
        "expenditure",
        "net_savings",
        "investment_gain_loss",
    ]
    flow_cols = inc_cols + exp_cols + [
        c for c in derived_flow_cols if c in df.columns
    ]
    
    # 2. Stocks (Last)
    cls_cols = [c for c in df.columns if c.startswith("分類_")]
    ast_cols = [c for c in df.columns if c.startswith("資産_")]
    stock_cols = cls_cols + ast_cols + ["liquid_assets", "risk_assets", "pension_assets", "total_financial_assets"]
    
    # Group by FY
    grouped = df.groupby("year")
    
    annual_flows = grouped[flow_cols].sum()
    annual_stocks = grouped[stock_cols].last()
    
    # Combine
    annual = pd.concat([annual_flows, annual_stocks], axis=1)
    
    # Recalculate Metrics
    # Savings Rate
    annual["savings_rate"] = 0.0
    mask = annual["after_tax_income"] != 0
    annual.loc[mask, "savings_rate"] = annual.loc[mask, "net_savings"] / annual.loc[mask, "after_tax_income"]
    
    # Risk Asset Ratio
    annual["risk_asset_ratio"] = 0.0
    mask = annual["total_financial_assets"] != 0
    annual.loc[mask, "risk_asset_ratio"] = (
        annual.loc[mask, "risk_assets"] + annual.loc[mask, "pension_assets"]
    ) / annual.loc[mask, "total_financial_assets"]
    
    # Annual return should compound the raw month-to-month returns.
    # `monthly_return` in this project is already a trailing-12m geometric
    # average, so reusing it here would double-smooth the result.
    def calc_annual_geo_return(raw_returns: pd.Series) -> float:
        raw_returns = raw_returns.dropna()
        if raw_returns.empty:
            return 0.0
        return float(np.prod(1 + raw_returns) - 1)

    annual_returns = grouped["raw_monthly_return"].apply(calc_annual_geo_return)
    annual["annual_return"] = annual_returns
    
    # Reset index to make 'year' a column
    annual = annual.reset_index()
    
    # Rounding (Same rules as forecast.csv)
    # Yen cols: 1000 round
    yen_prefixes = ("収入_", "支出_", "分類_", "資産_")
    numeric_cols = annual.select_dtypes(include=["float64", "int64"]).columns
    yen_cols = [c for c in numeric_cols if c.startswith(yen_prefixes)]
    
    # Others (Man-yen, Ratios): 4 sig figs
    # Note: Annual flows for income/expense are huge, Man-yen assets are large.
    sig_fig_cols = [c for c in numeric_cols if c not in yen_cols and c != "year"]
    
    for col in yen_cols:
        annual[col] = annual[col].apply(
            lambda x: round(x / 1000) * 1000 if pd.notna(x) else x
        )
        
    for col in sig_fig_cols:
        annual[col] = annual[col].apply(
            lambda x: float(f"{x:.4g}") if pd.notna(x) and x != 0 else x
        )
    
    # Reorder columns: year, 収入, 支出, cashflow, 資産, 分類, BS, metrics
    inc_cols_sorted = sorted([c for c in annual.columns if c.startswith("収入_")])
    exp_cols_sorted = sorted([c for c in annual.columns if c.startswith("支出_")])
    ast_cols_sorted = sorted([c for c in annual.columns if c.startswith("資産_")])
    cls_cols_sorted = sorted([c for c in annual.columns if c.startswith("分類_")])
    
    cashflow_cols = [
        "cash_income",
        "asset_contribution",
        "cash_savings",
        "net_worth_contribution",
        "after_tax_income",
        "expenditure",
        "net_savings",
    ]
    bs_cols = ["liquid_assets", "risk_assets", "pension_assets", "total_financial_assets", "investment_gain_loss"]
    metric_cols = ["savings_rate", "risk_asset_ratio", "annual_return"]
    
    col_order = ["year"] + inc_cols_sorted + exp_cols_sorted
    col_order += [c for c in cashflow_cols if c in annual.columns]
    col_order += ast_cols_sorted + cls_cols_sorted  # 資産 before 分類
    col_order += [c for c in bs_cols if c in annual.columns]
    col_order += [c for c in metric_cols if c in annual.columns]
    
    remaining = [c for c in annual.columns if c not in col_order]
    col_order += remaining
    
    annual = annual[col_order]
        
    # Export
    output_path = output_dir / "forecast_annual.csv"
    annual.to_csv(output_path, index=False)
    print(f"Exported annual summary to: {output_path}")


def main() -> None:
    """Generate 30-year financial forecast and concatenate with historical data."""
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    calculated_dir = data_dir / "calculated"
    
    # Load historical data
    # We load normalized.csv which has History (including metrics)
    history = pd.read_csv(calculated_dir / "normalized.csv")
    history["month"] = history["month"].apply(month_end_label)
    accounts = load_accounts(base_dir)
    streams = load_forecast_streams(base_dir)
    account_names = account_name_by_id(accounts)
    
    # Determine forecast period (next 30 years = 360 months)
    last_month = history["month"].max()
    last_period = month_period(last_month)
    future_months = [
        month_end_label((last_period + (i + 1)).strftime("%Y-%m"))
        for i in range(360)
    ]
    
    # Initialize forecast dataframe
    forecast = pd.DataFrame({"month": future_months})
    
    # Initialize stats collector
    stats = []
    
    # Get column categories
    income_cols = [c for c in history.columns if c.startswith("収入_")]
    expense_cols = [c for c in history.columns if c.startswith("支出_")]
    class_cols = [c for c in history.columns if c.startswith("分類_")]
    asset_cols = [c for c in history.columns if c.startswith("資産_")]
    
    # Forecast income by metadata stream, then write back to concrete columns.
    forecast_income, stream_amounts = forecast_income_by_stream(
        history, income_cols, future_months, accounts, streams, stats
    )
    for col in income_cols:
        forecast[col] = forecast["month"].map(forecast_income[col])
    
    # Forecast expenses
    for col in expense_cols:
        forecasts = forecast_expense(history, col, future_months, stats)
        forecast[col] = forecast["month"].map(forecasts)
    
    # Calculate cashflow (Raw values)
    kind_totals = stream_kind_totals(stream_amounts, streams)
    forecast["cash_income"] = forecast["month"].map(kind_totals["cash_income"]) / 10000
    forecast["asset_contribution"] = (
        forecast["month"].map(kind_totals["asset_contribution"]) / 10000
    )
    forecast["expenditure"] = forecast[expense_cols].sum(axis=1) / 10000
    forecast["cash_savings"] = forecast["cash_income"] - forecast["expenditure"]
    forecast["net_worth_contribution"] = (
        forecast["cash_savings"] + forecast["asset_contribution"]
    )
    forecast["after_tax_income"] = forecast["cash_income"]
    forecast["net_savings"] = forecast["cash_savings"]
    
    # Forecast assets
    # Get last values
    last_row = history.iloc[-1]
    
    # Calculate Geometric Mean Return from History for Risk Assets
    # (Re-enabling growth for Securities as per user implication)
    if "monthly_return" in history.columns:
        # Use last 12 months for estimation or last value
        valid_returns = history["monthly_return"].tail(12).dropna()
        if len(valid_returns) > 0:
            # Simple average or TTM geom? 
            # metrics.csv usually has 'monthly_return' as TTM Geometric Mean already?
            # src/use_cases/calculators/metrics.py: monthly_return IS TTM Geo Mean.
            # So we can just take the last valid value.
            val = history["monthly_return"].iloc[-1]
            if pd.notna(val) and val != 0:
                geo_return = val
            else:
                geo_return = EXPECTED_ANNUAL_RETURN / 12
        else:
             geo_return = EXPECTED_ANNUAL_RETURN / 12
    else:
        geo_return = EXPECTED_ANNUAL_RETURN / 12  # Default annual if no history
    
    stats.append({
        "category": "Asset",
        "item": "Risk Assets",
        "parameter": "geo_return",
        "value": float(f"{geo_return:.6f}"),
        "unit": "monthly_rate",
        "description": "Geometric Mean Return used for compounding"
    })
    
    # Define asset class categories for forecasting
    cash_classes = ["分類_現金・預金"]
    risk_classes = ["分類_投資信託", "分類_米国株", "分類_日本株", "分類_FX", "分類_暗号資産", "分類_VC"]
    pension_classes = ["分類_年金"]
    
    # Initialize previous values for 分類_* columns
    prev_class_values = {col: last_row.get(col, 0) for col in class_cols}
    prev_asset_values = {col: last_row.get(col, 0) for col in asset_cols}
    
    prev_liquid = last_row.get("liquid_assets", 0)
    prev_risk = last_row.get("risk_assets", 0)
    prev_pension = last_row.get("pension_assets", 0)
    cash_accounts, risk_accounts, pension_accounts = classify_asset_columns(
        asset_cols, accounts
    )
    contribution_income_by_asset = contribution_columns_by_asset(streams, account_names)
    target_cash_acc = preferred_cash_asset_column(
        streams, account_names, cash_accounts
    )
    
    for month_str in future_months:
        cash_savings = forecast.loc[
            forecast["month"] == month_str, "cash_savings"
        ].values[0]
        net_worth_contribution = forecast.loc[
            forecast["month"] == month_str, "net_worth_contribution"
        ].values[0]
        
        # Calculate Pension Contribution (Flow into Pension Assets)
        pension_contrib = forecast.loc[
            forecast["month"] == month_str, "asset_contribution"
        ].values[0]
        
        # Update Pension Assets (Contributions Only - Simplified)
        # (Pension is conservative, usually treated separately or fixed growth, here just contribs)
        new_pension = prev_pension + pension_contrib
        forecast.loc[forecast["month"] == month_str, "pension_assets"] = new_pension
        
        # Determine Liquid Flow (cash savings only; pension/DC is not spendable cash)
        liquid_flow = cash_savings
        
        # Logic: 
        # 1. Bank assets don't grow (Flat)
        # 2. Risk assets grow by Compounding Return (Capital Gains)
        # 3. Surplus flows to Risk Assets
        # 4. Deficit flows from Liquid Assets
        
        # Calculate Growth for Risk Assets first (Balance * Return)
        risk_growth = prev_risk * geo_return
        
        if liquid_flow > 0:
            # Surplus: Invest everything
            new_liquid = prev_liquid
            new_risk = prev_risk + risk_growth + liquid_flow
            
            class_delta_cash = 0
            class_delta_risk = liquid_flow # Flow part only (Growth added separately)
            
            account_delta_cash = 0
            account_delta_risk = liquid_flow
            
        else:
            # Deficit: Burn Cash
            new_liquid = prev_liquid + liquid_flow  # liquid_flow is negative
            new_risk = prev_risk + risk_growth # Still grows by return
            
            class_delta_cash = liquid_flow
            class_delta_risk = 0
            
            account_delta_cash = liquid_flow
            account_delta_risk = 0

        forecast.loc[forecast["month"] == month_str, "liquid_assets"] = new_liquid
        forecast.loc[forecast["month"] == month_str, "risk_assets"] = new_risk
        
        # Total assets
        total = new_liquid + new_risk + new_pension
        forecast.loc[forecast["month"] == month_str, "total_financial_assets"] = total
        
        # Investment gain/loss
        # Gain = Total - Prev - Net Worth Contribution
        # Gain ≈ Risk Growth
        prev_total = prev_liquid + prev_risk + prev_pension
        gain_loss = total - prev_total - net_worth_contribution
        forecast.loc[forecast["month"] == month_str, "investment_gain_loss"] = gain_loss
        
        # --- Update Class Columns ---
        target_risk_class = "分類_投資信託" # Default investment destination
        target_cash_class = "分類_現金・預金"
        
        for col in class_cols:
            new_val = prev_class_values[col]
            
            if col in pension_classes:
                new_val += pension_contrib * 10000
            elif col in risk_classes:
                # Apply Growth to ALL risk classes
                new_val = new_val * (1 + geo_return)
                # Add Flow if target
                if col == target_risk_class and class_delta_risk != 0:
                    new_val += class_delta_risk * 10000
            elif col in cash_classes:
                # No Growth
                # Add Flow if target
                if col == target_cash_class and class_delta_cash != 0:
                    new_val += class_delta_cash * 10000
            
            forecast.loc[forecast["month"] == month_str, col] = new_val
            prev_class_values[col] = new_val

        # --- Update Asset Columns ---
        current_risk_balances = {c: prev_asset_values.get(c, 0) for c in risk_accounts}
        if current_risk_balances:
            target_risk_acc = max(current_risk_balances, key=current_risk_balances.get)
        else:
            target_risk_acc = risk_accounts[0] if risk_accounts else None
        
        for col in asset_cols:
            new_val = prev_asset_values[col]
            
            if col in pension_accounts:
                contribution_col = contribution_income_by_asset.get(col)
                if contribution_col in forecast.columns:
                    new_val += forecast.loc[
                        forecast["month"] == month_str, contribution_col
                    ].values[0]
            
            elif col in risk_accounts:
                # Apply Growth to ALL risk accounts
                new_val = new_val * (1 + geo_return)
                # Add Flow if target
                if col == target_risk_acc and account_delta_risk != 0:
                    new_val += account_delta_risk * 10000
            
            elif col in cash_accounts:
                # No Growth
                # Add Flow if target
                if col == target_cash_acc and account_delta_cash != 0:
                    new_val += account_delta_cash * 10000
            
            forecast.loc[forecast["month"] == month_str, col] = new_val
            prev_asset_values[col] = new_val
        
        # Update for next iteration
        prev_liquid = new_liquid
        prev_risk = new_risk # (should be the calculated new_risk in loop)
        # Note: new_risk variable holds the updated total risk assets including growth and flow
        prev_risk = new_risk # Correct
        prev_pension = new_pension
    
    # --- METRICS CALCULATION (Using Unified Vectorized Logic) ---
    # 1. Combine History and Forecast (Raw values)
    # We append forecast to history
    if "cash_income" not in history.columns:
        history["cash_income"] = history["after_tax_income"]
    if "asset_contribution" not in history.columns:
        history["asset_contribution"] = 0.0
    if "cash_savings" not in history.columns:
        history["cash_savings"] = history["net_savings"]
    if "net_worth_contribution" not in history.columns:
        history["net_worth_contribution"] = history["net_savings"]

    combined = pd.concat([history, forecast], ignore_index=True)
    
    # 2. Calculate Derived Balance Sheet Items (Total, Gain/Loss)
    # This overwrites manually calculated values in loop with Strict Logic
    combined = calculate_bs_derived(combined)
    
    # 3. Calculate Derived Metrics on the Combined Dataframe
    # This ensures consistency with history and correct TTM calculations overlap
    combined = calculate_metrics_vectorized(combined, geo_return)
    
    # 4. Rounding
    # Keep raw income values exact; round the display-oriented columns only.
    numeric_cols = combined.select_dtypes(include=["float64", "int64"]).columns
    
    # Most yen-denominated columns are rounded for readability.
    # Income is left exact so the view matches the source input.
    yen_prefixes = ("収入_", "支出_", "分類_", "資産_")
    yen_cols = [
        c for c in numeric_cols if c.startswith(yen_prefixes) and not c.startswith("収入_")
    ]
    
    # Everything else is either Ratio or Man-yen amounts (liquid_assets, etc.)
    # User requested "4 significant figures" for these.
    # This covers: savings_rate, risk_asset_ratio, liquid_assets, risk_assets, 
    # investment_gain_loss, net_savings, etc.
    sig_fig_cols = [
        c for c in numeric_cols if c not in yen_cols and not c.startswith("収入_")
    ]
    
    # Special handling for monthly_alpha: threshold at 0.0001
    # User request: "monthly_alpha <= 0.0001 is zero"
    if "monthly_alpha" in combined.columns:
        combined.loc[combined["monthly_alpha"].abs() <= 0.0001, "monthly_alpha"] = 0.0
    
    # Apply rounding
    for col in yen_cols:
        combined[col] = combined[col].apply(
            lambda x: round(x / 1000) * 1000 if pd.notna(x) else x
        )
        
    for col in sig_fig_cols:
        combined[col] = combined[col].apply(
            lambda x: float(f"{x:.4g}") if pd.notna(x) and x != 0 else x
        )
    
    # 5. Reorder columns
    # Reconstruct order similarly to export_normalized.py
    
    # Categories
    income_cols = sorted([c for c in combined.columns if c.startswith("収入_")])
    expense_cols = sorted([c for c in combined.columns if c.startswith("支出_")])
    class_cols = sorted([c for c in combined.columns if c.startswith("分類_")])
    asset_cols = sorted([c for c in combined.columns if c.startswith("資産_")])
    
    cashflow_cols = [
        "cash_income",
        "asset_contribution",
        "cash_savings",
        "net_worth_contribution",
        "after_tax_income",
        "expenditure",
        "net_savings",
    ]
    bs_cols = ["liquid_assets", "risk_assets", "pension_assets", "total_financial_assets", "investment_gain_loss"]
    metric_cols = ["savings_rate", "risk_asset_ratio", "monthly_return", "monthly_alpha", 
                   "benchmark_return", "fi_ratio_12m", "fi_ratio_48m", "fi_ratio_next_12m"]
    
    col_order = ["month"] + income_cols + expense_cols
    col_order += [c for c in cashflow_cols if c in combined.columns]
    # Swap: Asset then Class
    col_order += asset_cols + class_cols
    col_order += [c for c in bs_cols if c in combined.columns]
    col_order += [c for c in metric_cols if c in combined.columns]
    
    # Add remaining
    remaining = [c for c in combined.columns if c not in col_order]
    col_order += remaining
    
    combined = combined[col_order]
    
    # Export combined data
    output_path = calculated_dir / "forecast.csv"
    combined.to_csv(output_path, index=False)
    print(f"Exported forecast to: {output_path}")
    print(f"Historical period: {history['month'].min()} to {history['month'].max()}")
    print(f"Forecast period: {future_months[0]} to {future_months[-1]}")
    print(f"Total rows: {len(combined)} (historical: {len(history)}, forecast: {len(forecast)})")
    
    # Generate Annual Summary
    export_annual_summary(combined, calculated_dir)
    
    # Sanity check metrics
    tail_metrics = combined[["month", "savings_rate", "risk_asset_ratio", "fi_ratio_12m"]].tail()
    print("\nForecast Metrics Preview:")
    print(tail_metrics)
    
    # Export stats
    stats_df = pd.DataFrame(stats)
    if not stats_df.empty:
        # Reorder columns
        stats_cols = ["category", "item", "parameter", "value", "unit", "description"]
        stats_df = stats_df[stats_cols]
        stats_path = calculated_dir / "forecast_parameters.csv"
        stats_df.to_csv(stats_path, index=False)
        print(f"Exported forecast parameters to: {stats_path}")


if __name__ == "__main__":
    main()
