from __future__ import annotations

import subprocess
from pathlib import Path

SENSITIVE_MASTER_PATHS = (
    "master/accounts.csv",
    "master/payment_methods.csv",
)
POLICY = Path("docs/private-master-migration.md")


def _history_for(path: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--all", "--format=%H", "--", path],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [line for line in result.stdout.splitlines() if line]


def _tracked_in_head(path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", path],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return path in result.stdout.splitlines()


def test_private_financial_masters_are_absent_from_current_tree() -> None:
    for path in SENSITIVE_MASTER_PATHS:
        assert not _tracked_in_head(path), f"private financial master is tracked: {path}"


def test_any_historical_exposure_is_explicitly_recorded_in_policy() -> None:
    policy = POLICY.read_text(encoding="utf-8")
    for path in SENSITIVE_MASTER_PATHS:
        commits = _history_for(path)
        if not commits:
            continue
        assert path in policy, f"history exposure path missing from policy: {path}"
        assert "履歴書換えを未実施" in policy
        assert "公開履歴から参照可能" in policy
