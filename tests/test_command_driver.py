from __future__ import annotations

import json
import sys
from pathlib import Path

from src.interface_adapters.command_driver import (
    CommandDriver,
    CommandDriverConfig,
    load_command_drivers,
)
from src.use_cases.finance_acquisition import SourcePolicy


def _policy() -> SourcePolicy:
    return SourcePolicy(
        source_id="provider",
        priority="P0",
        acquisition_method="official_csv",
        cadence_days=30,
        retention_days=60,
        safety_margin_days=10,
        official_reference="https://example.invalid",
    )


def _python_driver(payload: dict[str, object]) -> tuple[str, ...]:
    script = "import json; print(json.dumps(" + repr(payload) + "))"
    return (sys.executable, "-c", script)


def test_command_driver_reads_only_from_incoming_root(tmp_path: Path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    export = incoming / "利用明細.csv"
    export.write_bytes(b"a,b\n1,2\n")
    config = CommandDriverConfig(
        source_id="provider",
        argv=_python_driver(
            {
                "status": "SUCCESS",
                "path": str(export),
                "record_count": 1,
            }
        ),
    )
    result = CommandDriver(config, incoming_root=incoming).acquire(_policy())
    assert result.status == "SUCCESS"
    assert result.raw == b"a,b\n1,2\n"
    assert result.original_filename == "利用明細.csv"


def test_command_driver_rejects_export_outside_incoming_root(tmp_path: Path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    outside = tmp_path / "secret.csv"
    outside.write_text("secret", encoding="utf-8")
    config = CommandDriverConfig(
        source_id="provider",
        argv=_python_driver({"status": "SUCCESS", "path": str(outside)}),
    )
    result = CommandDriver(config, incoming_root=incoming).acquire(_policy())
    assert result.status == "FAILED"
    assert result.error_code == "EXPORT_OUTSIDE_INCOMING_ROOT"


def test_command_driver_preserves_auth_boundary(tmp_path: Path):
    config = CommandDriverConfig(
        source_id="provider",
        argv=_python_driver(
            {"status": "AUTH_REQUIRED", "error_code": "PASSKEY_REQUIRED"}
        ),
    )
    result = CommandDriver(config, incoming_root=tmp_path).acquire(_policy())
    assert result.status == "AUTH_REQUIRED"
    assert result.error_code == "PASSKEY_REQUIRED"


def test_driver_config_is_local_and_machine_readable(tmp_path: Path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    config_path = tmp_path / "drivers.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "wealthaudit.driver-commands.v1",
                "drivers": [
                    {
                        "source_id": "provider",
                        "argv": [sys.executable, "-c", "print('{}')"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    drivers = load_command_drivers(config_path, incoming_root=incoming)
    assert set(drivers) == {"provider"}
