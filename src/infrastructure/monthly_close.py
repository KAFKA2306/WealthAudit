from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pandas as pd

from src.use_cases.monthly_close import (
    AuditStatus,
    MonthlyCloseError,
    MonthlyCloseResult,
    MonthlyCloseStage,
)

REQUIRED_INPUT_COLUMNS: dict[str, set[str]] = {
    "income.csv": {"month", "account_id", "amount"},
    "expense.csv": {"month", "method_id", "amount"},
    "assets.csv": {"month", "account_id", "asset_class"},
    "market.csv": {"month", "usd_jpy", "eur_jpy", "sp500"},
}
CORE_CALCULATED_FILES = ("cashflow.csv", "balance_sheet.csv", "metrics.csv")
CALCULATION_TASKS = ("run", "export", "forecast")
COMMAND_TIMEOUT_SECONDS = 300
PASSTHROUGH_ENVIRONMENT = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")


class FilesystemMonthlyClosePort:
    """Filesystem adapter for the canonical monthly-close state machine."""

    def __init__(
        self,
        repo_root: Path,
        month: str,
        updates: Mapping[str, pd.DataFrame] | None = None,
        command_runner: Callable[[Sequence[str], Path], None] | None = None,
    ) -> None:
        if not month:
            raise ValueError("month is required")
        self.repo_root = repo_root.resolve()
        self.month = month
        self.input_dir = self.repo_root / "data" / "input"
        self.calculated_dir = self.repo_root / "data" / "calculated"
        self.state_path = self.repo_root / "data" / "state" / "monthly-close.json"
        self._lock_dir = self.repo_root / "data" / "state" / "monthly-close.lock"
        self._lock_token = uuid.uuid4().hex
        self._lock_acquired = False
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._acquire_lock()
        try:
            self._updates = dict(updates or {})
            self._command_runner = command_runner or self._run_command
            self._temporary = tempfile.TemporaryDirectory(
                prefix="wealthaudit-monthly-close-"
            )
            self._temp_root = Path(self._temporary.name)
            self._prepared_input = self._prepare_input()
            self._input_snapshot = self._snapshot_dir(self.input_dir, "input.original")
            self._calculated_snapshot = self._snapshot_dir(
                self.calculated_dir, "calculated.original"
            )
            self._collected = False
        except Exception:
            self._release_lock()
            raise

    def _acquire_lock(self) -> None:
        self._lock_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._lock_dir.mkdir()
        except FileExistsError as exc:
            raise MonthlyCloseError(
                "another monthly close is already in progress"
            ) from exc

        marker = self._lock_dir / "owner.json"
        try:
            marker.write_text(
                json.dumps(
                    {"pid": os.getpid(), "token": self._lock_token},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            self._lock_dir.rmdir()
            raise
        self._lock_acquired = True

    def _release_lock(self) -> None:
        if not self._lock_acquired:
            return
        marker = self._lock_dir / "owner.json"
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
            if payload.get("token") != self._lock_token:
                return
            marker.unlink()
            self._lock_dir.rmdir()
            self._lock_acquired = False
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            # Fail closed: never remove a lock whose ownership cannot be proven.
            return

    @staticmethod
    def _run_command(command: Sequence[str], cwd: Path) -> None:
        environment = {
            key: os.environ[key]
            for key in PASSTHROUGH_ENVIRONMENT
            if key in os.environ
        }
        environment.update(
            {
                "HOME": str(cwd),
                "USERPROFILE": str(cwd),
                "PYTHONNOUSERSITE": "1",
            }
        )
        subprocess.run(
            list(command),
            cwd=cwd,
            check=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            env=environment,
        )

    def _snapshot_dir(self, source: Path, name: str) -> Path | None:
        if not source.exists():
            return None
        destination = self._temp_root / name
        shutil.copytree(source, destination)
        return destination

    def _prepare_input(self) -> Path:
        prepared = self._temp_root / "input.prepared"
        if self.input_dir.exists():
            shutil.copytree(self.input_dir, prepared)
        else:
            prepared.mkdir(parents=True)
        for filename, frame in self._updates.items():
            frame.to_csv(prepared / filename, index=False)
        return prepared

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(self._prepared_input.glob("*.csv"), key=lambda item: item.name):
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def previous_result(self, fingerprint: str) -> MonthlyCloseResult | None:
        if not self.state_path.is_file():
            return None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if (
            payload.get("month") != self.month
            or payload.get("fingerprint") != fingerprint
            or payload.get("audit_status") != AuditStatus.PASS.value
        ):
            return None
        return MonthlyCloseResult(
            month=self.month,
            fingerprint=fingerprint,
            audit_status=AuditStatus.PASS,
            stages=tuple(MonthlyCloseStage(stage) for stage in payload.get("stages", [])),
        )

    def collect(self) -> None:
        self.input_dir.parent.mkdir(parents=True, exist_ok=True)
        if self.input_dir.exists():
            shutil.rmtree(self.input_dir)
        shutil.copytree(self._prepared_input, self.input_dir)
        self._collected = True

    def normalize(self) -> None:
        for filename, required in REQUIRED_INPUT_COLUMNS.items():
            path = self.input_dir / filename
            if not path.is_file():
                raise FileNotFoundError(f"required monthly input is missing: {path}")
            frame = pd.read_csv(path)
            missing = required - set(frame.columns)
            if missing:
                raise ValueError(
                    f"{filename} is missing required columns: {', '.join(sorted(missing))}"
                )
            if "month" in frame.columns and frame["month"].isna().any():
                raise ValueError(f"{filename} contains an empty month")

    def calculate(self) -> None:
        for task in CALCULATION_TASKS:
            self._command_runner(("task", task), self.repo_root)

    def audit(self) -> AuditStatus:
        self._command_runner(("task", "audit:recalculate"), self.repo_root)
        report_path = self.calculated_dir / "recalculation_diff.csv"
        if not report_path.is_file():
            return AuditStatus.FAIL
        report = pd.read_csv(report_path)
        if not report.empty:
            return AuditStatus.FAIL
        for filename in CORE_CALCULATED_FILES:
            path = self.calculated_dir / filename
            if not path.is_file():
                return AuditStatus.FAIL
            frame = pd.read_csv(path)
            if "month" not in frame.columns:
                return AuditStatus.FAIL
            target = frame[frame["month"].astype(str) == self.month]
            if len(target.index) != 1:
                return AuditStatus.FAIL
        return AuditStatus.PASS

    def close(self, fingerprint: str) -> None:
        payload = {
            "month": self.month,
            "fingerprint": fingerprint,
            "audit_status": AuditStatus.PASS.value,
            "stages": [stage.value for stage in MonthlyCloseStage],
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def rollback(self) -> None:
        if self._collected:
            self._restore_dir(self.input_dir, self._input_snapshot)
        self._restore_dir(self.calculated_dir, self._calculated_snapshot)

    @staticmethod
    def _restore_dir(destination: Path, snapshot: Path | None) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        if snapshot is not None:
            shutil.copytree(snapshot, destination)

    def cleanup(self) -> None:
        try:
            if self._temporary is not None:
                self._temporary.cleanup()
        finally:
            self._release_lock()
