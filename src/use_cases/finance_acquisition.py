from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

VALID_STATUSES = {
    "OK",
    "AUTH_REQUIRED",
    "FAILED",
    "SCHEMA_CHANGED",
    "GAP_DETECTED",
    "NEVER_RUN",
}


@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    priority: str
    acquisition_method: str
    cadence_days: int
    retention_days: int | None
    safety_margin_days: int
    official_reference: str
    max_records: int | None = None
    secondary_only: bool = False

    def effective_interval_days(self) -> int:
        if self.cadence_days <= 0:
            raise ValueError(f"{self.source_id}: cadence_days must be > 0")
        if self.safety_margin_days < 0:
            raise ValueError(f"{self.source_id}: safety_margin_days must be >= 0")
        if self.retention_days is None:
            return self.cadence_days
        usable_window = self.retention_days - self.safety_margin_days
        if usable_window <= 0:
            raise ValueError(
                f"{self.source_id}: retention_days must exceed safety_margin_days"
            )
        return min(self.cadence_days, usable_window)


@dataclass(frozen=True)
class SourceState:
    source_id: str
    status: str = "NEVER_RUN"
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    covered_from: str | None = None
    covered_to: str | None = None
    record_count: int = 0
    raw_file_count: int = 0
    last_raw_sha256: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {self.status}")


@dataclass(frozen=True)
class AcquisitionDecision:
    source_id: str
    action: str
    reason: str
    next_due_at: str | None


@dataclass(frozen=True)
class ArchivedArtifact:
    source_id: str
    account_alias: str
    acquired_at: str
    covered_from: str | None
    covered_to: str | None
    original_filename: str
    raw_sha256: str
    byte_size: int
    path: str
    created: bool


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def acquisition_decision(
    policy: SourcePolicy,
    state: SourceState | None,
    *,
    now: datetime | None = None,
) -> AcquisitionDecision:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    if state is None or state.status == "NEVER_RUN" or not state.last_success_at:
        return AcquisitionDecision(
            source_id=policy.source_id,
            action="ACQUIRE",
            reason="never_successfully_acquired",
            next_due_at=now.isoformat(),
        )

    if state.status == "AUTH_REQUIRED":
        return AcquisitionDecision(
            source_id=policy.source_id,
            action="WAIT_FOR_AUTH",
            reason="provider_requires_user_authentication",
            next_due_at=None,
        )

    if state.status in {"SCHEMA_CHANGED", "GAP_DETECTED"}:
        return AcquisitionDecision(
            source_id=policy.source_id,
            action="REVIEW_REQUIRED",
            reason=state.status.lower(),
            next_due_at=None,
        )

    last_success = _parse_timestamp(state.last_success_at)
    interval = timedelta(days=policy.effective_interval_days())
    due_at = last_success + interval

    if now >= due_at:
        return AcquisitionDecision(
            source_id=policy.source_id,
            action="ACQUIRE",
            reason="cadence_or_retention_guard_due",
            next_due_at=due_at.isoformat(),
        )

    return AcquisitionDecision(
        source_id=policy.source_id,
        action="NOOP",
        reason="fresh",
        next_due_at=due_at.isoformat(),
    )


def load_source_policies(path: Path) -> tuple[SourcePolicy, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "wealthaudit.finance-sources.v1":
        raise ValueError("unsupported finance source registry schema")
    policies = tuple(SourcePolicy(**item) for item in payload.get("sources", []))
    ids = [item.source_id for item in policies]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source_id in finance source registry")
    for policy in policies:
        policy.effective_interval_days()
    return policies


def load_source_state(path: Path, source_id: str) -> SourceState:
    if not path.exists():
        return SourceState(source_id=source_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("source_id") != source_id:
        raise ValueError(f"state source mismatch for {source_id}")
    return SourceState(**payload)


def save_source_state(path: Path, state: SourceState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n")


def _safe_segment(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = normalized.strip("._")
    if not normalized:
        raise ValueError("empty or unsafe path segment")
    return normalized[:120]


def _safe_filename(value: str) -> str:
    original = Path(value).name
    path = Path(original)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._")
    if not stem:
        stem = "artifact"
    suffix = re.sub(r"[^A-Za-z0-9.]+", "", "".join(path.suffixes))
    return f"{stem[:96]}{suffix[:24]}"


def archive_raw_artifact(
    *,
    root: Path,
    source_id: str,
    account_alias: str,
    raw: bytes,
    original_filename: str,
    acquired_at: str | None = None,
    covered_from: str | None = None,
    covered_to: str | None = None,
) -> ArchivedArtifact:
    acquired = _parse_timestamp(acquired_at) if acquired_at else datetime.now(timezone.utc)
    digest = hashlib.sha256(raw).hexdigest()
    source = _safe_segment(source_id)
    account = _safe_segment(account_alias)
    filename = _safe_filename(original_filename)
    day = acquired.date().isoformat()
    relative = Path("raw") / source / account / day / f"{digest[:16]}_{filename}"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)

    created = False
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("existing raw artifact hash mismatch")
    else:
        _atomic_write_bytes(target, raw)
        created = True

    manifest = {
        "schema_version": "wealthaudit.raw-artifact.v1",
        "source_id": source_id,
        "account_alias": account_alias,
        "acquired_at": acquired.isoformat(),
        "covered_from": covered_from,
        "covered_to": covered_to,
        "original_filename": Path(original_filename).name,
        "raw_sha256": digest,
        "byte_size": len(raw),
        "path": relative.as_posix(),
    }
    manifest_path = root / "state" / "artifacts" / f"{digest}.json"
    if not manifest_path.exists():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(
            manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )

    return ArchivedArtifact(
        source_id=source_id,
        account_alias=account_alias,
        acquired_at=acquired.isoformat(),
        covered_from=covered_from,
        covered_to=covered_to,
        original_filename=Path(original_filename).name,
        raw_sha256=digest,
        byte_size=len(raw),
        path=relative.as_posix(),
        created=created,
    )


def mark_auth_required(
    state: SourceState,
    *,
    attempted_at: str | None = None,
    error_code: str = "AUTH_REQUIRED",
) -> SourceState:
    return SourceState(
        source_id=state.source_id,
        status="AUTH_REQUIRED",
        last_attempt_at=attempted_at or datetime.now(timezone.utc).isoformat(),
        last_success_at=state.last_success_at,
        covered_from=state.covered_from,
        covered_to=state.covered_to,
        record_count=state.record_count,
        raw_file_count=state.raw_file_count,
        last_raw_sha256=state.last_raw_sha256,
        error_code=error_code,
    )


def mark_failed(
    state: SourceState,
    *,
    attempted_at: str | None = None,
    error_code: str = "ACQUISITION_FAILED",
) -> SourceState:
    return SourceState(
        source_id=state.source_id,
        status="FAILED",
        last_attempt_at=attempted_at or datetime.now(timezone.utc).isoformat(),
        last_success_at=state.last_success_at,
        covered_from=state.covered_from,
        covered_to=state.covered_to,
        record_count=state.record_count,
        raw_file_count=state.raw_file_count,
        last_raw_sha256=state.last_raw_sha256,
        error_code=error_code,
    )


def mark_success(
    state: SourceState,
    artifact: ArchivedArtifact,
    *,
    record_count: int,
) -> SourceState:
    return SourceState(
        source_id=state.source_id,
        status="OK",
        last_attempt_at=artifact.acquired_at,
        last_success_at=artifact.acquired_at,
        covered_from=artifact.covered_from or state.covered_from,
        covered_to=artifact.covered_to or state.covered_to,
        record_count=record_count,
        raw_file_count=state.raw_file_count + (1 if artifact.created else 0),
        last_raw_sha256=artifact.raw_sha256,
        error_code=None,
    )


def coverage_rows(
    policies: tuple[SourcePolicy, ...],
    *,
    state_dir: Path,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows: list[dict[str, Any]] = []
    for policy in policies:
        state = load_source_state(state_dir / f"{policy.source_id}.json", policy.source_id)
        decision = acquisition_decision(policy, state, now=current)
        stale_days = None
        if state.last_success_at:
            stale_days = max(0, (current - _parse_timestamp(state.last_success_at)).days)
        coverage_status = {
            "NOOP": "OK",
            "ACQUIRE": "DUE",
            "WAIT_FOR_AUTH": "AUTH_REQUIRED",
            "REVIEW_REQUIRED": "REVIEW_REQUIRED",
        }[decision.action]
        rows.append(
            {
                "source_id": policy.source_id,
                "priority": policy.priority,
                "status": state.status,
                "coverage_status": coverage_status,
                "action": decision.action,
                "reason": decision.reason,
                "last_success_at": state.last_success_at,
                "covered_from": state.covered_from,
                "covered_to": state.covered_to,
                "record_count": state.record_count,
                "raw_file_count": state.raw_file_count,
                "stale_days": stale_days,
                "next_due_at": decision.next_due_at,
            }
        )
    return rows


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _atomic_write_text(path: Path, payload: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
