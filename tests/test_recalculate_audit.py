from pathlib import Path

import pytest

from scripts.recalculate_audit import REQUIRED_INPUT_FILES, require_operational_inputs


def test_recalculation_audit_reports_missing_private_inputs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as error:
        require_operational_inputs(tmp_path)

    message = str(error.value)
    assert "Operational input data is required" in message
    assert "task drive:import" in message
    assert "WEALTHAUDIT_DRIVE_DIR" in message
    for relative_path in REQUIRED_INPUT_FILES:
        assert relative_path in message


def test_recalculation_audit_accepts_complete_input_set(tmp_path: Path) -> None:
    for relative_path in REQUIRED_INPUT_FILES:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("header\n")

    require_operational_inputs(tmp_path)
