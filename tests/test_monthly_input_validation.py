from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.infrastructure.monthly_input_validation import validate_monthly_input


def _validate(payload: dict[str, object]):
    return validate_monthly_input(
        payload,
        allowed_account_ids={"bank_main", "broker_main", "fx_multi"},
        allowed_method_ids={"card_main", "cash"},
        allowed_asset_classes={"cash", "equity", "fund"},
        account_currencies={
            "bank_main": "JPY",
            "broker_main": "JPY",
            "fx_multi": "multi",
        },
    )


def test_accepts_known_bank_and_securities_accounts() -> None:
    model = _validate(
        {
            "target_month": "2026-08",
            "income": [{"account_id": "bank_main", "amount": 500000}],
            "expenses": [{"method_id": "card_main", "amount": 120000}],
            "assets": [
                {
                    "account_id": "bank_main",
                    "asset_class": "cash",
                    "balance": 1200000,
                    "native_currency": "JPY",
                },
                {
                    "account_id": "broker_main",
                    "asset_class": "equity",
                    "balance": 3500000,
                    "native_currency": "JPY",
                },
            ],
        }
    )

    assert len(model.assets) == 2


def test_rejects_unknown_account_before_persistence() -> None:
    with pytest.raises(ValueError, match="unknown account_id"):
        _validate(
            {
                "target_month": "2026-08",
                "assets": [
                    {
                        "account_id": "attacker_account",
                        "asset_class": "cash",
                        "balance": 1,
                        "native_currency": "JPY",
                    }
                ],
            }
        )


def test_rejects_unknown_payment_method_and_asset_class() -> None:
    with pytest.raises(ValueError, match="unknown method_id"):
        _validate(
            {
                "target_month": "2026-08",
                "expenses": [{"method_id": "unknown", "amount": 1}],
            }
        )

    with pytest.raises(ValueError, match="unknown asset_class"):
        _validate(
            {
                "target_month": "2026-08",
                "assets": [
                    {
                        "account_id": "broker_main",
                        "asset_class": "option_contract",
                        "balance": 1,
                        "native_currency": "JPY",
                    }
                ],
            }
        )


def test_rejects_bad_month_negative_or_extreme_values() -> None:
    with pytest.raises(ValidationError):
        _validate({"target_month": "2026-13"})

    with pytest.raises(ValidationError):
        _validate(
            {
                "target_month": "2026-08",
                "income": [{"account_id": "bank_main", "amount": -1}],
            }
        )


def test_multi_currency_account_requires_explicit_iso_currency() -> None:
    with pytest.raises(ValueError, match="native_currency is required"):
        _validate(
            {
                "target_month": "2026-08",
                "assets": [
                    {
                        "account_id": "fx_multi",
                        "asset_class": "cash",
                        "balance": 100,
                        "native_currency": "",
                    }
                ],
            }
        )
