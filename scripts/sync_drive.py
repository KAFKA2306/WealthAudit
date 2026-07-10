"""Local XLSX boundary for Drive-synced WealthAudit files."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DRIVE_DIR_ENV = "WEALTHAUDIT_DRIVE_DIR"
INPUT_WORKBOOK = "input.xlsx"
VIEW_WORKBOOK = "view.xlsx"

REQUIRED_INPUT_COLUMNS: dict[str, tuple[str, ...]] = {
    "income": ("month", "account_id", "amount"),
    "expense": ("month", "method_id", "amount"),
    "assets": ("month", "account_id", "asset_class", "balance"),
    "market": ("month", "usd_jpy", "eur_jpy", "sp500"),
}
PREFERRED_EXPORT_SHEETS = (
    "cashflow",
    "balance_sheet",
    "metrics",
    "normalized",
    "forecast",
)


class SyncDriveError(RuntimeError):
    """Raised when local workbook conversion cannot proceed."""


def resolve_drive_dir(drive_dir: str | None) -> Path:
    configured = drive_dir or os.environ.get(DRIVE_DIR_ENV)
    return Path(configured).expanduser().resolve() if configured else REPO_ROOT


def read_input_workbook(path: Path) -> dict[str, pd.DataFrame]:
    if not path.exists():
        raise SyncDriveError(f"Input workbook not found: {path}")

    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    missing_sheets = sorted(set(REQUIRED_INPUT_COLUMNS) - set(sheets))
    if missing_sheets:
        raise SyncDriveError(
            "Input workbook is missing required sheets: " + ", ".join(missing_sheets)
        )

    selected: dict[str, pd.DataFrame] = {}
    validation_errors: list[str] = []
    for sheet, required_columns in REQUIRED_INPUT_COLUMNS.items():
        frame = sheets[sheet]
        missing_columns = [
            column for column in required_columns if column not in frame.columns
        ]
        if missing_columns:
            validation_errors.append(
                f"{sheet}: missing columns {', '.join(missing_columns)}"
            )
        selected[sheet] = frame

    if validation_errors:
        raise SyncDriveError(
            "Input workbook failed validation: " + "; ".join(validation_errors)
        )

    return selected


def atomic_write_csv(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        frame.to_csv(temp_path, index=False)
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def import_input_workbook(drive_dir: Path, repo_root: Path = REPO_ROOT) -> list[Path]:
    sheets = read_input_workbook(drive_dir / INPUT_WORKBOOK)
    input_dir = repo_root / "data" / "input"
    written: list[Path] = []

    for sheet, frame in sheets.items():
        destination = input_dir / f"{sheet}.csv"
        atomic_write_csv(frame, destination)
        written.append(destination)

    return written


def calculated_csvs(repo_root: Path = REPO_ROOT) -> list[Path]:
    calculated_dir = repo_root / "data" / "calculated"
    if not calculated_dir.exists():
        return []

    by_stem = {path.stem: path for path in calculated_dir.glob("*.csv")}
    ordered = [
        by_stem.pop(sheet) for sheet in PREFERRED_EXPORT_SHEETS if sheet in by_stem
    ]
    ordered.extend(by_stem[name] for name in sorted(by_stem))
    return ordered


def sheet_name_for(path: Path) -> str:
    sheet_name = path.stem[:31]
    if not sheet_name:
        raise SyncDriveError(f"Cannot derive sheet name from calculated CSV: {path}")
    return sheet_name


def export_view_workbook(drive_dir: Path, repo_root: Path = REPO_ROOT) -> Path:
    csv_paths = calculated_csvs(repo_root)
    if not csv_paths:
        raise SyncDriveError(
            f"No calculated CSVs found under {repo_root / 'data' / 'calculated'}"
        )

    sheet_names = [sheet_name_for(path) for path in csv_paths]
    duplicates = {
        sheet_name for sheet_name in sheet_names if sheet_names.count(sheet_name) > 1
    }
    if duplicates:
        raise SyncDriveError(
            "Calculated CSV names collide as Excel sheet names: "
            + ", ".join(sorted(duplicates))
        )

    destination = drive_dir / VIEW_WORKBOOK
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=".xlsx", dir=destination.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
            for csv_path in csv_paths:
                pd.read_csv(csv_path).to_excel(
                    writer, sheet_name=sheet_name_for(csv_path), index=False
                )
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert local Drive-synced input.xlsx/view.xlsx files without Google "
            "APIs, OAuth, service accounts, or network calls."
        ),
        epilog=(
            f"Drive directory resolution: --drive-dir, then {DRIVE_DIR_ENV}, "
            "then the repository root."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("import", "Import input.xlsx sheets into data/input/*.csv"),
        ("export", "Export data/calculated/*.csv into view.xlsx"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--drive-dir",
            help=(
                f"Directory containing {INPUT_WORKBOOK} and receiving "
                f"{VIEW_WORKBOOK}; defaults to {DRIVE_DIR_ENV} or repo root."
            ),
        )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    drive_dir = resolve_drive_dir(args.drive_dir)

    try:
        if args.command == "import":
            written = import_input_workbook(drive_dir)
            for path in written:
                print(f"Imported {path}")
            return 0

        if args.command == "export":
            destination = export_view_workbook(drive_dir)
            print(f"Exported {destination}")
            return 0
    except SyncDriveError as exc:
        parser.exit(2, f"error: {exc}\n")

    parser.exit(2, f"error: unknown command {args.command}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
