from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.infrastructure.source_adapter_monthly import execute_source_monthly_close
from src.use_cases.monthly_close import MonthlyCloseError, MonthlyCloseStage
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

    def __init__(
        self,
        auth_result: AuthResult | None = None,
        *,
        amount: int = 100,
    ) -> None:
        self.auth_result = auth_result or AuthResult("success", context=object())
        self.amount = amount
        self.fetch_calls = 0

    def authenticate(self) -> AuthResult:
        return self.auth_result

    def fetch(self, auth_context, target_month: str) -> bytes:
        assert auth_context is not None
        self.fetch_calls += 1
        return json.dumps({"month": target_month, "amount": self.amount}).encode()

    def parse(self, raw: bytes):
        return [json.loads(raw)]

    def normalize(self, records, target_month: str):
        return {
            "income": [
                {
                    "month": target_month,
                    "account_id": "bank",
                    "amount": records[0]["amount"],
                }
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
            income = pd.read_csv(cwd / "data" / "input" / "income.csv")
            amount = int(income["amount"].sum())
            for filename in ("cashflow.csv", "balance_sheet.csv", "metrics.csv"):
                pd.DataFrame([{"month": month, "value": amount}]).to_csv(
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
    assert pd.read_csv(tmp_path / "data" / "calculated" / "cashflow.csv")[
        "value"
    ].tolist() == [100]


def test_same_source_payload_is_idempotent(tmp_path: Path) -> None:
    first_calls: list[tuple[str, ...]] = []
    execute_source_monthly_close(
        _MonthlyFixtureAdapter(),
        tmp_path,
        "2026-07",
        known_accounts={"bank"},
        known_payment_methods=set(),
        fetched_at="2026-08-10T00:00:00+00:00",
        command_runner=_successful_runner("2026-07", first_calls),
    )

    replay_calls: list[tuple[str, ...]] = []
    replay = execute_source_monthly_close(
        _MonthlyFixtureAdapter(),
        tmp_path,
        "2026-07",
        known_accounts={"bank"},
        known_payment_methods=set(),
        fetched_at="2026-08-10T00:00:00+00:00",
        command_runner=_successful_runner("2026-07", replay_calls),
    )

    assert replay.reused is True
    assert replay_calls == []
    assert pd.read_csv(tmp_path / "data" / "input" / "income.csv")["amount"].tolist() == [
        100
    ]


def test_monthly_failure_keeps_previous_closed_state_and_provenance(tmp_path: Path) -> None:
    execute_source_monthly_close(
        _MonthlyFixtureAdapter(amount=100),
        tmp_path,
        "2026-07",
        known_accounts={"bank"},
        known_payment_methods=set(),
        fetched_at="2026-08-10T00:00:00+00:00",
        command_runner=_successful_runner("2026-07", []),
    )
    source_state_path = tmp_path / "data" / "state" / "source-monthly-fixture.json"
    close_state_path = tmp_path / "data" / "state" / "monthly-close.json"
    previous_source = source_state_path.read_text(encoding="utf-8")
    previous_close = close_state_path.read_text(encoding="utf-8")

    def fail_calculation(command, cwd: Path) -> None:
        if tuple(command) == ("task", "run"):
            calculated = cwd / "data" / "calculated"
            calculated.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([{"month": "2026-07", "value": 999}]).to_csv(
                calculated / "cashflow.csv", index=False
            )
            raise RuntimeError("controlled calculation failure")

    with pytest.raises(MonthlyCloseError, match="calculate"):
        execute_source_monthly_close(
            _MonthlyFixtureAdapter(amount=200),
            tmp_path,
            "2026-07",
            known_accounts={"bank"},
            known_payment_methods=set(),
            fetched_at="2026-08-11T00:00:00+00:00",
            command_runner=fail_calculation,
        )

    assert pd.read_csv(tmp_path / "data" / "input" / "income.csv")["amount"].tolist() == [
        100
    ]
    assert pd.read_csv(tmp_path / "data" / "calculated" / "cashflow.csv")[
        "value"
    ].tolist() == [100]
    assert source_state_path.read_text(encoding="utf-8") == previous_source
    assert close_state_path.read_text(encoding="utf-8") == previous_close


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
