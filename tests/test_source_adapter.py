from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.use_cases.source_adapter import (
    SourceAdapter,
    SourceAdapterError,
    validate_normalized_tables,
    write_provenance,
)


class _FixtureAdapter(SourceAdapter):
    source_id = "fixture"

    def authenticate(self):
        return object()

    def fetch(self, auth_context, target_month: str) -> bytes:
        del auth_context
        return json.dumps({"month": target_month, "amount": 100}).encode()

    def parse(self, raw: bytes):
        return [json.loads(raw)]

    def normalize(self, records, target_month: str):
        del records
        return {
            "income": [{"month": target_month, "account_id": "bank", "amount": 100}],
            "expense": [],
            "assets": [],
            "market": [],
        }


def test_run_returns_canonical_tables_and_provenance():
    result = _FixtureAdapter().run(
        "2026-07",
        known_accounts={"bank"},
        known_payment_methods=set(),
        retrieved_at="2026-08-10T00:00:00+00:00",
    )
    assert result.provenance.source_id == "fixture"
    assert result.provenance.target_month == "2026-07"
    assert result.provenance.record_count == 1
    assert len(result.provenance.raw_sha256) == 64
    assert set(result.tables) == {"income", "expense", "assets", "market"}


def test_unknown_account_fails_closed():
    with pytest.raises(SourceAdapterError, match="unknown account_id"):
        validate_normalized_tables(
            {"income": [{"month": "2026-07", "account_id": "ghost", "amount": 1}]},
            target_month="2026-07",
            known_accounts={"bank"},
            known_payment_methods=set(),
        )


def test_duplicate_identity_fails_closed():
    row = {"month": "2026-07", "account_id": "bank", "amount": 1}
    with pytest.raises(SourceAdapterError, match="duplicate income identity"):
        validate_normalized_tables(
            {"income": [row, dict(row)]},
            target_month="2026-07",
            known_accounts={"bank"},
            known_payment_methods=set(),
        )


def test_missing_fields_and_wrong_month_fail_closed():
    with pytest.raises(SourceAdapterError, match="missing fields"):
        validate_normalized_tables(
            {"market": [{"month": "2026-07"}]},
            target_month="2026-07",
            known_accounts=set(),
            known_payment_methods=set(),
        )
    with pytest.raises(SourceAdapterError, match="!="):
        validate_normalized_tables(
            {"expense": [{"month": "2026-06", "method_id": "card", "amount": 1}]},
            target_month="2026-07",
            known_accounts=set(),
            known_payment_methods={"card"},
        )


def test_provenance_writer_contains_only_audit_metadata(tmp_path: Path):
    result = _FixtureAdapter().run(
        "2026-07",
        known_accounts={"bank"},
        known_payment_methods=set(),
        retrieved_at="2026-08-10T00:00:00+00:00",
    )
    path = tmp_path / "data" / "state" / "source-fixture.json"
    write_provenance(path, result.provenance)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "source_id",
        "retrieved_at",
        "target_month",
        "record_count",
        "raw_sha256",
    }
    assert "token" not in path.read_text(encoding="utf-8").lower()
