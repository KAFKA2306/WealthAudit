from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from src.infrastructure.monthly_close import (
    COMMAND_TIMEOUT_SECONDS,
    FilesystemMonthlyClosePort,
)


def test_default_command_runner_bounds_time_and_environment(tmp_path: Path) -> None:
    os.environ["WEALTHAUDIT_SECRET_SENTINEL"] = "must-not-propagate"

    with patch("src.infrastructure.monthly_close.subprocess.run") as run:
        FilesystemMonthlyClosePort._run_command(("task", "run"), tmp_path)

    kwargs = run.call_args.kwargs
    assert kwargs["cwd"] == tmp_path
    assert kwargs["check"] is True
    assert kwargs["timeout"] == COMMAND_TIMEOUT_SECONDS
    assert kwargs["env"]["HOME"] == str(tmp_path)
    assert kwargs["env"]["USERPROFILE"] == str(tmp_path)
    assert kwargs["env"]["PYTHONNOUSERSITE"] == "1"
    assert "WEALTHAUDIT_SECRET_SENTINEL" not in kwargs["env"]


def test_timeout_is_not_swallowed(tmp_path: Path) -> None:
    with patch(
        "src.infrastructure.monthly_close.subprocess.run",
        side_effect=subprocess.TimeoutExpired(("task", "run"), COMMAND_TIMEOUT_SECONDS),
    ):
        try:
            FilesystemMonthlyClosePort._run_command(("task", "run"), tmp_path)
        except subprocess.TimeoutExpired as exc:
            assert exc.timeout == COMMAND_TIMEOUT_SECONDS
        else:
            raise AssertionError("timeout must fail closed")
