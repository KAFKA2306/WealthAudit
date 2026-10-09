from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.use_cases.source_adapter import (
    AuthResult,
    SourceAdapter,
    SourceAdapterError,
    SourceAuthenticationError,
    SourceContract,
    validate_normalized_tables,
    write_provenance,
)


class _FixtureAdapter(SourceAdapter):
    contract = SourceContract(
        source_id="fixture",
        acquisition_method="controlled_fixture",
        auth_mode="delegated",
        supported_period="monthly",
        provenance="https://example.invalid/source-contract",
    )

    def __init__(self, auth_result: AuthResult | None = None) -> None:
        self.auth_result = auth_result or AuthResult("success", context=object())
        self.fetch_calls = 0

    def authenticate(self) -> AuthResult:
        return self.auth_result

    def fetch(self, auth_context, target_month: str) -> bytes:
        assert auth_context is not None
        self.fetch_calls += 1
        return json.dumps(
            {
                "month": target_month,
                "amount": 100,
                "published_at": "2026-08-01T00:00:00Z",
            }
        ).encode()

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

    def source_published_at(self, records):
        return records[0]["published_at"]


def test_run_returns_canonical_tables_and_versionable_provenance():
    result = _FixtureAdapter().run(
        "2026-07",
        known_accounts={"bank"},
        known_payment_methods=set(),
        fetched_at="2026-08-10T00:00:00+00:00",
    )
    assert result.provenance.source_id == "fixture"
    assert result.provenance.acquisition_method == "controlled_fixture"
    assert result.provenance.auth_mode == "delegated"
    assert result.provenance.supported_period == "monthly"
    assert result.provenance.fetched_at == "2026-08-10T00:00:00+00:00"
    assert result.provenance.source_published_at == "2026-08-01T00:00:00Z"
    assert result.provenance.status == "success"
    assert result.provenance.runtime_verification == "UNVERIFIED"
    assert result.provenance.raw_record_count == 1
    assert result.provenance.record_count == 1
    assert result.provenance.table_record_counts == {
        "income": 1,
        "expense": 0,
        "assets": 0,
        "market": 0,
    }
    assert len(result.provenance.content_hash) == 64
    assert set(result.tables) == {"income", "expense", "assets", "market"}


@pytest.mark.parametrize("status", ["cancel", "timeout", "failure", "unavailable"])
def test_non_success_auth_never_fetches(status):
    adapter = _FixtureAdapter(AuthResult(status, reason=f"fixture {status}"))
    with pytest.raises(SourceAuthenticationError) as exc_info:
        adapter.run(
            "2026-07",
            known_accounts={"bank"},
            known_payment_methods=set(),
        )
    assert exc_info.value.status == status
    assert adapter.fetch_calls == 0


def test_auth_result_rejects_ambiguous_context():
    with pytest.raises(SourceAdapterError, match="requires context"):
        AuthResult("success")
    with pytest.raises(SourceAdapterError, match="must not carry context"):
        AuthResult("cancel", context=object())


def test_adapter_rejects_legacy_opaque_auth_result():
    class _LegacyAdapter(_FixtureAdapter):
        def authenticate(self):
            return object()

    with pytest.raises(SourceAdapterError, match="must return AuthResult"):
        _LegacyAdapter().run(
            "2026-07",
            known_accounts={"bank"},
            known_payment_methods=set(),
        )


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
        fetched_at="2026-08-10T00:00:00+00:00",
    )
    path = tmp_path / "data" / "state" / "source-fixture.json"
    write_provenance(path, result.provenance)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "source_id",
        "acquisition_method",
        "auth_mode",
        "supported_period",
        "fetched_at",
        "source_published_at",
        "provenance",
        "record_count",
        "raw_record_count",
        "table_record_counts",
        "content_hash",
        "status",
        "runtime_verification",
    }
    serialized = path.read_text(encoding="utf-8").lower()
    assert "token" not in serialized
    assert "password" not in serialized
    assert "otp" not in serialized
