from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from src.use_cases.finance_acquisition import SourcePolicy
from src.use_cases.finance_runner import AcquisitionDriver, DriverResult


@dataclass(frozen=True)
class CommandDriverConfig:
    source_id: str
    argv: tuple[str, ...]
    timeout_seconds: int = 300
    working_directory: str | None = None


class CommandDriver(AcquisitionDriver):
    """Run a local provider acquisition command without invoking a shell."""

    def __init__(self, config: CommandDriverConfig, *, incoming_root: Path) -> None:
        if not config.argv:
            raise ValueError("driver argv must not be empty")
        if config.timeout_seconds <= 0:
            raise ValueError("driver timeout_seconds must be > 0")
        self.config = config
        self.incoming_root = incoming_root.resolve()

    def acquire(self, policy: SourcePolicy) -> DriverResult:
        if policy.source_id != self.config.source_id:
            raise ValueError("driver/source mismatch")

        completed = subprocess.run(
            list(self.config.argv),
            cwd=self.config.working_directory,
            capture_output=True,
            text=True,
            check=False,
            timeout=self.config.timeout_seconds,
            shell=False,
        )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            if completed.returncode != 0:
                return DriverResult(
                    status="FAILED",
                    error_code=f"DRIVER_EXIT_{completed.returncode}",
                )
            return DriverResult(status="FAILED", error_code="INVALID_DRIVER_JSON")

        status = str(payload.get("status", "FAILED"))
        if status == "AUTH_REQUIRED":
            return DriverResult(
                status="AUTH_REQUIRED",
                error_code=str(payload.get("error_code") or "AUTH_REQUIRED"),
            )

        if completed.returncode != 0:
            return DriverResult(
                status="FAILED",
                error_code=f"DRIVER_EXIT_{completed.returncode}",
            )

        if status != "SUCCESS":
            return DriverResult(
                status="FAILED",
                error_code=str(payload.get("error_code") or status),
            )

        path_value = payload.get("path")
        if not isinstance(path_value, str) or not path_value:
            return DriverResult(status="FAILED", error_code="MISSING_EXPORT_PATH")

        export_path = Path(path_value).expanduser().resolve()
        try:
            export_path.relative_to(self.incoming_root)
        except ValueError:
            return DriverResult(status="FAILED", error_code="EXPORT_OUTSIDE_INCOMING_ROOT")
        if not export_path.is_file():
            return DriverResult(status="FAILED", error_code="EXPORT_FILE_MISSING")

        return DriverResult(
            status="SUCCESS",
            raw=export_path.read_bytes(),
            original_filename=str(payload.get("original_filename") or export_path.name),
            account_alias=str(payload.get("account_alias") or "default"),
            covered_from=_optional_string(payload.get("covered_from")),
            covered_to=_optional_string(payload.get("covered_to")),
            record_count=int(payload.get("record_count") or 0),
        )


def load_command_drivers(
    path: Path,
    *,
    incoming_root: Path,
) -> Mapping[str, CommandDriver]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "wealthaudit.driver-commands.v1":
        raise ValueError("unsupported driver command schema")

    result: dict[str, CommandDriver] = {}
    for item in payload.get("drivers", []):
        source_id = str(item["source_id"])
        if source_id in result:
            raise ValueError(f"duplicate command driver: {source_id}")
        config = CommandDriverConfig(
            source_id=source_id,
            argv=tuple(str(value) for value in item.get("argv", [])),
            timeout_seconds=int(item.get("timeout_seconds", 300)),
            working_directory=_optional_string(item.get("working_directory")),
        )
        result[source_id] = CommandDriver(config, incoming_root=incoming_root)
    return result


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
