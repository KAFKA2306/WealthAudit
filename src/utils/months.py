from __future__ import annotations

import pandas as pd


def month_end_label(value: str) -> str:
    """Normalize a month-like label to the last day of that month."""
    return pd.Timestamp(value).to_period("M").to_timestamp(how="end").strftime("%Y-%m-%d")


def next_month_end_label(value: str) -> str:
    """Return the last day of the month after the given month-like label."""
    period = pd.Timestamp(value).to_period("M") + 1
    return period.to_timestamp(how="end").strftime("%Y-%m-%d")


def month_period(value: str) -> pd.Period:
    """Convert a month-like label to a monthly Period."""
    return pd.Timestamp(value).to_period("M")
