from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.infrastructure.source_adapter_monthly import execute_source_monthly_close
from src.use_cases.monthly_close import MonthlyCloseStage
from src.use_cases.source_adapter import (
    AuthResult,
    SourceAdapter,
    SourceAuthenticationError,
    SourceContract,
)


class _MonthlyFixtureAdapter(SourceAdapter):
    contract = SourceContract(
        source_id="monthly-fixture",
        acquisition_method="controlled_fixture",
        auth_mode="delegated",
        supported_period="monthly",
        provenance="https://example.invalid/monthly-fixture",
    )

    def __init__(self, auth_result: AuthResult | None = None) -> None:
        self.auth_result = auth_result or AuthResult("success", context=object())
        self.fetch_calls = 0

    def authenticate(self) -> AuthResult:
        return self.auth_result

    def fetch(self, auth_context, target_month: str) -> bytes:
        assert auth_context is not None
        self.fetch_calls += 1
        return json.dumps({"month": target_month, "amount": 100}).encode()

    def parse(self, raw: bytes):
        return [json.loads(raw)]

    def normalize(self, records, target_month: str):
        del records
        return {
            "income": [
                {"month": target_month, "account_id": "bank", "amount": 100}
            ],
            "expense": [],
            "assets": [],
            "market": [],
        }


def _successful_runner(month: str, calls: list[tuple[str, ...]]):
    def run(command, cwd: Path) -> None:
        calls.append(tuple(command))
        calculated = cwd / "data" / "calculated"
        calculated.mkdir(parents=True, exist_ok=True)
        if tuple(command) == ("task", "run"):
            for filename in ("cashflow.csv", "balance_sheet.csv", "metrics.csv"):
                pd.DataFrame([{"month": month, "value": 1}]).to_csv(
                    calculated / filename, index=False
                )
        elif tuple(command) == ("task", "audit:recalculate"):
            pd.DataFrame(
                columns=["file", "key", "column", "before", "after", "delta"]
            ).to_csv(calculated / "recalculation_diff.csv", index=False)

    return run


def test_source_adapter_flows_into_canonical_monthly_close(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    adapter = _MonthlyFixtureAdapter()

    result = execute_source_monthly_close(
        adapter,
        tmp_path,
        "2026-07",
        known_accounts={"bank"},
        known_payment_methods=set(),
        fetched_at="2026-08-10T00:00:00+00:00",
        command_runner=_successful_runner("2026-07", calls),
    )

    assert adapter.fetch_calls == 1
    assert result.stages == tuple(MonthlyCloseStage)
    assert calls == [
        ("task", "run"),
        ("task", "export"),
        ("task", "forecast"),
        ("task", "audit:recalculate"),
    ]
    source_state = json.loads(
        (tmp_path / "data" / "state" / "source-monthly-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    close_state = json.loads(
        (tmp_path / "data" / "state" / "monthly-close.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_state["status"] == "success"
    assert source_state["record_count"] == 1
    assert close_state["audit_status"] == "PASS"
    assert pd.read_csv(tmp_path / "data" / "input" / "income.csv")["amount"].tolist() == [
        100
    ]


@pytest.mark.parametrize("status", ["cancel", "timeout", "failure", "unavailable"])
def test_failed_auth_never_starts_monthly_close(tmp_path: Path, status: str) -> None:
    calls: list[tuple[str, ...]] = []
    adapter = _MonthlyFixtureAdapter(AuthResult(status, reason="controlled outcome"))

    with pytest.raises(SourceAuthenticationError):
        execute_source_monthly_close(
            adapter,
            tmp_path,
            "2026-07",
            known_accounts={"bank"},
            known_payment_methods=set(),
            command_runner=_successful_runner("2026-07", calls),
        )

    assert adapter.fetch_calls == 0
    assert calls == []
    assert not (tmp_path / "data").exists()
