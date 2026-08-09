from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class MonthlyCloseStage(StrEnum):
    COLLECT = "collect"
    NORMALIZE = "normalize"
    CALCULATE = "calculate"
    AUDIT = "audit"
    CLOSE = "close"


class AuditStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class MonthlyCloseError(RuntimeError):
    """Raised when a monthly close cannot safely reach CLOSE."""


@dataclass(frozen=True)
class MonthlyCloseResult:
    month: str
    fingerprint: str
    audit_status: AuditStatus
    stages: tuple[MonthlyCloseStage, ...]
    reused: bool = False


class MonthlyClosePort(Protocol):
    month: str

    def fingerprint(self) -> str: ...
    def previous_result(self, fingerprint: str) -> MonthlyCloseResult | None: ...
    def collect(self) -> None: ...
    def normalize(self) -> None: ...
    def calculate(self) -> None: ...
    def audit(self) -> AuditStatus: ...
    def close(self, fingerprint: str) -> None: ...
    def rollback(self) -> None: ...
    def cleanup(self) -> None: ...


class MonthlyCloseWorkflow:
    """Canonical collect -> normalize -> calculate -> audit -> close state machine."""

    def execute(self, port: MonthlyClosePort) -> MonthlyCloseResult:
        started = False
        active_stage: MonthlyCloseStage | None = None
        try:
            fingerprint = port.fingerprint()
            previous = port.previous_result(fingerprint)
            if previous is not None:
                return MonthlyCloseResult(
                    month=previous.month,
                    fingerprint=previous.fingerprint,
                    audit_status=previous.audit_status,
                    stages=previous.stages,
                    reused=True,
                )

            started = True
            completed: list[MonthlyCloseStage] = []

            active_stage = MonthlyCloseStage.COLLECT
            port.collect()
            completed.append(active_stage)

            active_stage = MonthlyCloseStage.NORMALIZE
            port.normalize()
            completed.append(active_stage)

            active_stage = MonthlyCloseStage.CALCULATE
            port.calculate()
            completed.append(active_stage)

            active_stage = MonthlyCloseStage.AUDIT
            audit_status = port.audit()
            completed.append(active_stage)
            if audit_status is not AuditStatus.PASS:
                raise MonthlyCloseError(
                    f"monthly close audit failed for {port.month}; CLOSE was not executed"
                )

            active_stage = MonthlyCloseStage.CLOSE
            port.close(fingerprint)
            completed.append(active_stage)
            return MonthlyCloseResult(
                month=port.month,
                fingerprint=fingerprint,
                audit_status=audit_status,
                stages=tuple(completed),
            )
        except Exception as exc:
            if started:
                port.rollback()
            if isinstance(exc, MonthlyCloseError):
                raise
            stage = active_stage.value if active_stage is not None else "prepare"
            raise MonthlyCloseError(f"monthly close failed during {stage}: {exc}") from exc
        finally:
            port.cleanup()
