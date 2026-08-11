from datetime import date
from decimal import Decimal

import pytest

from src.domain.asset_ledger import (
    Account,
    AccountType,
    Asset,
    AssetKind,
    AssetLedger,
    BalanceSnapshot,
    Holding,
    Institution,
    Valuation,
    reconcile_asset_ledger,
)


def make_ledger() -> AssetLedger:
    return AssetLedger(
        institutions=[
            Institution(institution_id="inst_bank"),
            Institution(institution_id="inst_broker"),
            Institution(institution_id="inst_fintech"),
            Institution(institution_id="inst_crypto"),
            Institution(institution_id="inst_pension"),
        ],
        accounts=[
            Account(
                account_id="acct_bank",
                institution_id="inst_bank",
                account_type=AccountType.BANK,
                currency="JPY",
            ),
            Account(
                account_id="acct_broker",
                institution_id="inst_broker",
                account_type=AccountType.SECURITIES,
                currency="JPY",
            ),
            Account(
                account_id="acct_fintech",
                institution_id="inst_fintech",
                account_type=AccountType.FINTECH,
                currency="JPY",
            ),
            Account(
                account_id="acct_crypto",
                institution_id="inst_crypto",
                account_type=AccountType.CRYPTO,
                currency="JPY",
            ),
            Account(
                account_id="acct_pension",
                institution_id="inst_pension",
                account_type=AccountType.PENSION,
                currency="JPY",
            ),
        ],
        assets=[
            Asset(asset_id="JP0000000001", kind=AssetKind.EQUITY, currency="JPY"),
            Asset(asset_id="BTC", kind=AssetKind.CRYPTO, currency="JPY"),
            Asset(asset_id="PENSION_FUND", kind=AssetKind.PENSION, currency="JPY"),
        ],
        holdings=[
            Holding(
                account_id="acct_broker",
                asset_id="JP0000000001",
                quantity=Decimal(10),
            ),
            Holding(
                account_id="acct_crypto",
                asset_id="BTC",
                quantity=Decimal("0.1"),
            ),
            Holding(
                account_id="acct_pension",
                asset_id="PENSION_FUND",
                quantity=Decimal(1),
            ),
        ],
        balance_snapshots=[
            BalanceSnapshot(
                account_id="acct_bank",
                balance=Decimal(1000000),
                currency="JPY",
                balance_date=date(2026, 7, 31),
                source_revision="sha256:bank",
            ),
            BalanceSnapshot(
                account_id="acct_broker",
                balance=Decimal(200000),
                currency="JPY",
                balance_date=date(2026, 7, 31),
                source_revision="sha256:broker-cash",
            ),
            BalanceSnapshot(
                account_id="acct_fintech",
                balance=Decimal(50000),
                currency="JPY",
                balance_date=date(2026, 7, 31),
                source_revision="sha256:fintech",
            ),
            BalanceSnapshot(
                account_id="acct_crypto",
                balance=Decimal(10000),
                currency="JPY",
                balance_date=date(2026, 7, 31),
                source_revision="sha256:crypto-cash",
            ),
            BalanceSnapshot(
                account_id="acct_pension",
                balance=Decimal(0),
                currency="JPY",
                balance_date=date(2026, 7, 31),
                source_revision="sha256:pension-cash",
            ),
        ],
        valuations=[
            Valuation(
                account_id="acct_broker",
                asset_id="JP0000000001",
                value=Decimal(3000000),
                currency="JPY",
                valuation_date=date(2026, 7, 31),
                source_revision="sha256:equity",
            ),
            Valuation(
                account_id="acct_crypto",
                asset_id="BTC",
                value=Decimal(900000),
                currency="JPY",
                valuation_date=date(2026, 7, 31),
                source_revision="sha256:btc",
            ),
            Valuation(
                account_id="acct_pension",
                asset_id="PENSION_FUND",
                value=Decimal(2500000),
                currency="JPY",
                valuation_date=date(2026, 7, 31),
                source_revision="sha256:pension",
            ),
        ],
    )


def test_reconciliation_keeps_bank_and_broker_cash_separate() -> None:
    result = reconcile_asset_ledger(make_ledger(), as_of=date(2026, 7, 31))

    assert result.subtotals[AccountType.BANK] == Decimal(1000000)
    assert result.subtotals[AccountType.SECURITIES] == Decimal(3200000)
    assert result.subtotals[AccountType.FINTECH] == Decimal(50000)
    assert result.subtotals[AccountType.CRYPTO] == Decimal(910000)
    assert result.subtotals[AccountType.PENSION] == Decimal(2500000)
    assert result.total_assets == Decimal(7660000)
    assert result.problems == []


def test_missing_valuation_is_unknown_not_zero() -> None:
    ledger = make_ledger()
    ledger.valuations = [
        item for item in ledger.valuations if item.asset_id != "JP0000000001"
    ]

    result = reconcile_asset_ledger(ledger, as_of=date(2026, 7, 31))

    assert result.subtotals[AccountType.SECURITIES] is None
    assert result.total_assets is None
    assert any("missing valuation" in problem for problem in result.problems)


def test_valuation_date_mismatch_is_not_silently_reused() -> None:
    result = reconcile_asset_ledger(make_ledger(), as_of=date(2026, 8, 31))

    assert result.total_assets is None
    assert result.problems
    assert any("missing balance_snapshot" in problem for problem in result.problems)


def test_unknown_references_fail_closed() -> None:
    ledger = make_ledger().model_dump()
    ledger["holdings"][0]["account_id"] = "missing_account"

    with pytest.raises(ValueError, match="holding references unknown"):
        AssetLedger.model_validate(ledger)
