"""Recalculate the full pipeline and export a before/after numeric audit."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

REQUIRED_INPUT_FILES = (
    "data/input/income.csv",
    "data/input/expense.csv",
    "data/input/assets.csv",
    "data/input/market.csv",
)
CALCULATED_FILES = (
    "cashflow.csv",
    "balance_sheet.csv",
    "metrics.csv",
    "normalized.csv",
    "forecast.csv",
    "forecast_annual.csv",
)
PIPELINE = (
    ("python", "-m", "src.infrastructure.cli"),
    ("python", "scripts/export_normalized.py"),
    ("python", "scripts/forecast.py"),
)


def require_operational_inputs(repo_root: Path) -> None:
    """Fail early when the private, gitignored operational dataset is absent."""
    missing = [path for path in REQUIRED_INPUT_FILES if not (repo_root / path).is_file()]
    if not missing:
        return
    formatted = "\n".join(f"  - {path}" for path in missing)
    raise FileNotFoundError(
        "Operational input data is required for the recalculation audit but is "
        "not present:\n"
        f"{formatted}\n"
        "The data/ directory is intentionally excluded from Git. Restore "
        "data/input from the private Drive source first, for example with "
        "`task drive:import` after configuring WEALTHAUDIT_DRIVE_DIR, then run "
        "`task audit:recalculate` again."
    )


def compare_csv(before: Path, after: Path, filename: str) -> pd.DataFrame:
    if not before.exists() or not after.exists():
        return pd.DataFrame()
    old = pd.read_csv(before)
    new = pd.read_csv(after)
    key = "month" if "month" in old.columns and "month" in new.columns else "year"
    if key not in old.columns or key not in new.columns:
        return pd.DataFrame()
    merged = old.merge(new, on=key, how="outer", suffixes=("_before", "_after"))
    records: list[dict[str, object]] = []
    common = sorted((set(old.columns) & set(new.columns)) - {key})
    for column in common:
        before_values = pd.to_numeric(merged[f"{column}_before"], errors="coerce")
        after_values = pd.to_numeric(merged[f"{column}_after"], errors="coerce")
        changed = ~(before_values.fillna(0.0).eq(after_values.fillna(0.0)))
        for index in merged.index[changed]:
            before_value = before_values.loc[index]
            after_value = after_values.loc[index]
            records.append(
                {
                    "file": filename,
                    "key": merged.loc[index, key],
                    "column": column,
                    "before": before_value,
                    "after": after_value,
                    "delta": after_value - before_value,
                }
            )
    return pd.DataFrame.from_records(records)


def run_pipeline(repo_root: Path) -> None:
    for command in PIPELINE:
        subprocess.run(command, cwd=repo_root, check=True)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    require_operational_inputs(repo_root)
    calculated = repo_root / "data" / "calculated"
    calculated.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wealthaudit-before-") as temporary:
        snapshot = Path(temporary)
        for filename in CALCULATED_FILES:
            source = calculated / filename
            if source.exists():
                shutil.copy2(source, snapshot / filename)

        run_pipeline(repo_root)

        differences = [
            compare_csv(snapshot / filename, calculated / filename, filename)
            for filename in CALCULATED_FILES
        ]
        differences = [frame for frame in differences if not frame.empty]
        report = (
            pd.concat(differences, ignore_index=True)
            if differences
            else pd.DataFrame(
                columns=["file", "key", "column", "before", "after", "delta"]
            )
        )
        report.to_csv(calculated / "recalculation_diff.csv", index=False)
        print(
            f"Exported {calculated / 'recalculation_diff.csv'} "
            f"with {len(report)} changed numeric cells"
        )


if __name__ == "__main__":
    main()
