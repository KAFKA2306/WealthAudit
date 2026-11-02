from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol

from src.use_cases.finance_acquisition import (
    SourcePolicy,
    acquisition_decision,
    archive_raw_artifact,
    load_source_state,
    mark_auth_required,
    mark_failed,
    mark_success,
    save_source_state,
)


@dataclass(frozen=True)
class DriverResult:
    status: str
    raw: bytes | None = None
    original_filename: str | None = None
    account_alias: str = "default"
    covered_from: str | None = None
    covered_to: str | None = None
    record_count: int = 0
    error_code: str | None = None


class AcquisitionDriver(Protocol):
    def acquire(self, policy: SourcePolicy) -> DriverResult:
        """Return official raw bytes or an explicit authentication boundary."""


def run_acquisition_cycle(
    policies: tuple[SourcePolicy, ...],
    *,
    drivers: Mapping[str, AcquisitionDriver],
    data_root: Path,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    state_dir = data_root / "state" / "sources"
    outcomes: list[dict[str, object]] = []

    for policy in policies:
        state_path = state_dir / f"{policy.source_id}.json"
        state = load_source_state(state_path, policy.source_id)
        decision = acquisition_decision(policy, state, now=current)

        if decision.action != "ACQUIRE":
            outcomes.append(
                {
                    "source_id": policy.source_id,
                    "result": decision.action,
                    "reason": decision.reason,
                }
            )
            continue

        driver = drivers.get(policy.source_id)
        if driver is None:
            outcomes.append(
                {
                    "source_id": policy.source_id,
                    "result": "DRIVER_MISSING",
                    "reason": "no acquisition driver registered",
                }
            )
            continue

        try:
            result = driver.acquire(policy)
            if result.status == "AUTH_REQUIRED":
                updated = mark_auth_required(
                    state,
                    attempted_at=current.isoformat(),
                    error_code=result.error_code or "AUTH_REQUIRED",
                )
                save_source_state(state_path, updated)
                outcomes.append(
                    {
                        "source_id": policy.source_id,
                        "result": "AUTH_REQUIRED",
                        "reason": updated.error_code,
                    }
                )
                continue

            if result.status != "SUCCESS":
                updated = mark_failed(
                    state,
                    attempted_at=current.isoformat(),
                    error_code=result.error_code or result.status,
                )
                save_source_state(state_path, updated)
                outcomes.append(
                    {
                        "source_id": policy.source_id,
                        "result": "FAILED",
                        "reason": updated.error_code,
                    }
                )
                continue

            if result.raw is None or not result.original_filename:
                raise ValueError("SUCCESS result requires raw and original_filename")

            artifact = archive_raw_artifact(
                root=data_root,
                source_id=policy.source_id,
                account_alias=result.account_alias,
                raw=result.raw,
                original_filename=result.original_filename,
                acquired_at=current.isoformat(),
                covered_from=result.covered_from,
                covered_to=result.covered_to,
            )
            updated = mark_success(
                state,
                artifact,
                record_count=result.record_count,
            )
            save_source_state(state_path, updated)
            outcomes.append(
                {
                    "source_id": policy.source_id,
                    "result": "SUCCESS",
                    "created_raw": artifact.created,
                    "raw_sha256": artifact.raw_sha256,
                }
            )
        except Exception as exc:
            updated = mark_failed(
                state,
                attempted_at=current.isoformat(),
                error_code=type(exc).__name__,
            )
            save_source_state(state_path, updated)
            outcomes.append(
                {
                    "source_id": policy.source_id,
                    "result": "FAILED",
                    "reason": type(exc).__name__,
                }
            )

    return outcomes
