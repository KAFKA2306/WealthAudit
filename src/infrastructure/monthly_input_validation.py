"""Fail-closed validation for monthly financial inputs."""

from __future__ import annotations

import datetime as dt
import math
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MAX_ROWS_PER_SECTION = 500
MAX_AMOUNT = 1_000_000_000_000
MAX_BALANCE = 1_000_000_000_000_000.0


class IncomeRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=64)
    amount: int = Field(ge=0, le=MAX_AMOUNT)


class ExpenseRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_id: str = Field(min_length=1, max_length=64)
    amount: int = Field(ge=0, le=MAX_AMOUNT)


class AssetRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    balance: float = Field(ge=0, le=MAX_BALANCE)
    native_currency: str = Field(default="", max_length=3, pattern=r"^(|[A-Z]{3})$")

    @field_validator("balance")
    @classmethod
    def finite_balance(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("balance must be finite")
        return value


class MonthlyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    income: list[IncomeRow] = Field(default_factory=list, max_length=MAX_ROWS_PER_SECTION)
    expenses: list[ExpenseRow] = Field(default_factory=list, max_length=MAX_ROWS_PER_SECTION)
    assets: list[AssetRow] = Field(default_factory=list, max_length=MAX_ROWS_PER_SECTION)

    @field_validator("target_month")
    @classmethod
    def valid_calendar_month(cls, value: str) -> str:
        dt.datetime.strptime(value, "%Y-%m")
        return value


def _unknown(values: Iterable[str], allowed: set[str]) -> list[str]:
    return sorted(set(values) - allowed)


def validate_monthly_input(
    payload: dict[str, object],
    *,
    allowed_account_ids: set[str],
    allowed_method_ids: set[str],
    allowed_asset_classes: set[str],
    account_currencies: dict[str, str],
) -> MonthlyInput:
    """Validate syntax, ranges, master IDs, asset classes and account currencies."""

    model = MonthlyInput.model_validate(payload)

    unknown_accounts = _unknown(
        [row.account_id for row in model.income]
        + [row.account_id for row in model.assets],
        allowed_account_ids,
    )
    if unknown_accounts:
        raise ValueError(f"unknown account_id: {', '.join(unknown_accounts)}")

    unknown_methods = _unknown(
        [row.method_id for row in model.expenses], allowed_method_ids
    )
    if unknown_methods:
        raise ValueError(f"unknown method_id: {', '.join(unknown_methods)}")

    unknown_asset_classes = _unknown(
        [row.asset_class for row in model.assets], allowed_asset_classes
    )
    if unknown_asset_classes:
        raise ValueError(
            f"unknown asset_class: {', '.join(unknown_asset_classes)}"
        )

    for row in model.assets:
        configured = account_currencies.get(row.account_id, "")
        if configured == "multi" and not row.native_currency:
            raise ValueError(
                f"native_currency is required for multi-currency account {row.account_id}"
            )
        if configured not in {"", "multi"} and row.native_currency not in {"", configured}:
            raise ValueError(
                f"native_currency does not match account {row.account_id}"
            )

    return model


__all__ = [
    "AssetRow",
    "ExpenseRow",
    "IncomeRow",
    "MonthlyInput",
    "ValidationError",
    "validate_monthly_input",
]
