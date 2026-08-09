from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.infrastructure.monthly_close import FilesystemMonthlyClosePort
from src.use_cases.monthly_close import (
    AuditStatus,
    MonthlyCloseError,
    MonthlyCloseStage,
    MonthlyCloseWorkflow,
)


class FakePort:
    month = "2026-07"

    def __init__(
        self,
        audit_status: AuditStatus = AuditStatus.PASS,
        fail_stage: str | None = None,
    ) -> None:
        self.audit_status = audit_status
        self.fail_stage = fail_stage
        self.calls: list[str] = []

    def _record(self, stage: str) -> None:
        self.calls.append(stage)
        if self.fail_stage == stage:
            raise RuntimeError(f"{stage} failed")

    def fingerprint(self) -> str:
        return "abc"

    def previous_result(self, fingerprint: str):
        return None

    def collect(self) -> None:
        self._record("collect")

    def normalize(self) -> None:
        self._record("normalize")

    def calculate(self) -> None:
        self._record("calculate")

    def audit(self) -> AuditStatus:
        self._record("audit")
        return self.audit_status

    def close(self, fingerprint: str) -> None:
        self._record("close")

    def rollback(self) -> None:
        self.calls.append("rollback")

    def cleanup(self) -> None:
        self.calls.append("cleanup")


def _write_inputs(root: Path, month: str = "2026-07") -> None:
    input_dir = root / "data" / "input"
    input_dir.mkdir(parents=True)
    pd.DataFrame([{"month": month, "account_id": "salary", "amount": 1}]).to_csv(
        input_dir / "income.csv", index=False
    )
    pd.DataFrame([{"month": month, "method_id": "cash", "amount": 1}]).to_csv(
        input_dir / "expense.csv", index=False
    )
    pd.DataFrame(
        [{"month": month, "account_id": "bank", "asset_class": "cash", "balance": 1}]
    ).to_csv(input_dir / "assets.csv", index=False)
    pd.DataFrame([{"month": month, "usd_jpy": 1, "eur_jpy": 1, "sp500": 1}]).to_csv(
        input_dir / "market.csv", index=False
    )


def _output_runner(month: str, calls: list[tuple[str, ...]]):
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


def test_workflow_uses_exact_five_state_order() -> None:
    port = FakePort()
    result = MonthlyCloseWorkflow().execute(port)

    assert result.stages == tuple(MonthlyCloseStage)
    assert port.calls == ["collect", "normalize", "calculate", "audit", "close", "cleanup"]


def test_audit_failure_never_closes_and_rolls_back() -> None:
    port = FakePort(AuditStatus.FAIL)

    with pytest.raises(MonthlyCloseError):
        MonthlyCloseWorkflow().execute(port)

    assert "close" not in port.calls
    assert port.calls[-2:] == ["rollback", "cleanup"]


@pytest.mark.parametrize("stage", ["collect", "normalize", "calculate", "audit", "close"])
def test_each_state_failure_rolls_back_and_stops(stage: str) -> None:
    port = FakePort(fail_stage=stage)

    with pytest.raises(MonthlyCloseError, match=stage):
        MonthlyCloseWorkflow().execute(port)

    assert port.calls[-2:] == ["rollback", "cleanup"]
    ordered = ["collect", "normalize", "calculate", "audit", "close"]
    failure_index = ordered.index(stage)
    for later in ordered[failure_index + 1 :]:
        assert later not in port.calls


def test_same_input_reuses_closed_result_without_recalculation(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    first_calls: list[tuple[str, ...]] = []
    first = FilesystemMonthlyClosePort(
        tmp_path,
        "2026-07",
        command_runner=_output_runner("2026-07", first_calls),
    )
    first_result = MonthlyCloseWorkflow().execute(first)
    assert first_result.reused is False
    assert len(first_calls) == 4

    second_calls: list[tuple[str, ...]] = []
    second = FilesystemMonthlyClosePort(
        tmp_path,
        "2026-07",
        command_runner=_output_runner("2026-07", second_calls),
    )
    second_result = MonthlyCloseWorkflow().execute(second)
    assert second_result.reused is True
    assert second_calls == []

    state = json.loads(
        (tmp_path / "data" / "state" / "monthly-close.json").read_text(encoding="utf-8")
    )
    assert state["audit_status"] == "PASS"


def test_calculation_failure_restores_inputs_and_calculated(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    calculated = tmp_path / "data" / "calculated"
    calculated.mkdir(parents=True)
    original = pd.DataFrame([{"month": "2026-06", "value": 7}])
    original.to_csv(calculated / "cashflow.csv", index=False)
    replacement = pd.DataFrame([{"month": "2026-07", "account_id": "salary", "amount": 2}])

    def fail(command, cwd: Path) -> None:
        raise RuntimeError("calculation failed")

    port = FilesystemMonthlyClosePort(
        tmp_path,
        "2026-07",
        updates={"income.csv": replacement},
        command_runner=fail,
    )

    with pytest.raises(MonthlyCloseError, match="calculate"):
        MonthlyCloseWorkflow().execute(port)

    restored_income = pd.read_csv(tmp_path / "data" / "input" / "income.csv")
    restored_calculated = pd.read_csv(calculated / "cashflow.csv")
    assert restored_income["amount"].tolist() == [1]
    assert restored_calculated["value"].tolist() == [7]
    assert not (tmp_path / "data" / "state" / "monthly-close.json").exists()
