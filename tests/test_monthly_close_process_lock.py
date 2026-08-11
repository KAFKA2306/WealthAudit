from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.infrastructure.monthly_close import FilesystemMonthlyClosePort
from src.use_cases.monthly_close import MonthlyCloseError


def test_monthly_close_process_lock_is_exclusive_and_released(tmp_path: Path) -> None:
    first = FilesystemMonthlyClosePort(repo_root=tmp_path, month="2026-08")
    lock_dir = tmp_path / "data" / "state" / "monthly-close.lock"
    marker = lock_dir / "owner.json"

    assert lock_dir.is_dir()
    owner = json.loads(marker.read_text(encoding="utf-8"))
    assert owner["pid"] == os.getpid()
    assert owner["token"]

    with pytest.raises(MonthlyCloseError, match="already in progress"):
        FilesystemMonthlyClosePort(repo_root=tmp_path, month="2026-08")

    first.cleanup()
    assert not lock_dir.exists()

    second = FilesystemMonthlyClosePort(repo_root=tmp_path, month="2026-08")
    second.cleanup()
    assert not lock_dir.exists()


def test_monthly_close_cleanup_does_not_remove_unowned_lock(tmp_path: Path) -> None:
    port = FilesystemMonthlyClosePort(repo_root=tmp_path, month="2026-08")
    lock_dir = tmp_path / "data" / "state" / "monthly-close.lock"
    marker = lock_dir / "owner.json"
    marker.write_text('{"pid": 999999, "token": "different-owner"}\n', encoding="utf-8")

    port.cleanup()

    assert lock_dir.is_dir()
    assert marker.is_file()
