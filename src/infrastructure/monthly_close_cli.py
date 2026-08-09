from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.infrastructure.monthly_close import FilesystemMonthlyClosePort
from src.use_cases.monthly_close import MonthlyCloseWorkflow


def latest_input_month(repo_root: Path) -> str:
    path = repo_root / "data" / "input" / "income.csv"
    if not path.is_file():
        raise FileNotFoundError(f"monthly income input is missing: {path}")
    frame = pd.read_csv(path)
    if frame.empty or "month" not in frame.columns:
        raise ValueError("income.csv must contain at least one month")
    return str(frame["month"].astype(str).max())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the canonical WealthAudit monthly close")
    parser.add_argument(
        "month",
        nargs="?",
        help="target month; defaults to the latest month in data/input/income.csv",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    month = args.month or latest_input_month(repo_root)
    result = MonthlyCloseWorkflow().execute(
        FilesystemMonthlyClosePort(repo_root=repo_root, month=month)
    )
    suffix = " (reused)" if result.reused else ""
    print(f"Monthly close {month}: {result.audit_status.value}{suffix}")


if __name__ == "__main__":
    main()
