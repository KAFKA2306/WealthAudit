"""Local XLSX boundary for Drive-synced WealthAudit files."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class DoctorReport:
    messages: tuple[str, ...]
    blocking_issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.blocking_issues


@dataclass(frozen=True)
class FileOperationResult:
    directory: Path
    files: tuple[Path, ...]


class SyncDriveError(RuntimeError):
    """Raised when local workbook conversion cannot proceed."""


def resolve_drive_dir(drive_dir: str | None) -> Path:
    configured = drive_dir or os.environ.get(DRIVE_DIR_ENV)
    return Path(configured).expanduser().resolve() if configured else REPO_ROOT


def resolve_user_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


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


def detect_conflict_files(drive_dir: Path) -> list[Path]:
    if not drive_dir.exists() or not drive_dir.is_dir():
        return []

    conflicts: list[Path] = []
    for path in sorted(drive_dir.iterdir()):
        name = path.name
        lower_name = name.lower()
        if "conflicted copy" in lower_name:
            conflicts.append(path)
        elif name.startswith("~$") and path.suffix.lower() == ".xlsx":
            conflicts.append(path)
        elif lower_name.endswith(".tmp"):
            conflicts.append(path)
    return conflicts


def verify_writable_dir(path: Path) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=".wealthaudit-doctor.", suffix=".tmp", dir=path
    )
    os.close(fd)
    Path(temp_name).unlink(missing_ok=True)


def doctor_drive(drive_dir: Path) -> DoctorReport:
    messages: list[str] = []
    blocking_issues: list[str] = []

    if not drive_dir.exists():
        blocking_issues.append(f"Drive directory does not exist: {drive_dir}")
    elif not drive_dir.is_dir():
        blocking_issues.append(f"Drive path is not a directory: {drive_dir}")
    else:
        messages.append(f"OK drive directory exists: {drive_dir}")
        try:
            verify_writable_dir(drive_dir)
            messages.append(f"OK drive directory is writable: {drive_dir}")
        except OSError as exc:
            blocking_issues.append(
                f"Drive directory is not writable: {drive_dir}: {exc}"
            )

        conflicts = detect_conflict_files(drive_dir)
        if conflicts:
            for path in conflicts:
                blocking_issues.append(f"Conflict/temp file present: {path}")
        else:
            messages.append("OK no Drive/Excel conflict or temp files detected")

    input_workbook = drive_dir / INPUT_WORKBOOK
    if input_workbook.exists():
        try:
            read_input_workbook(input_workbook)
            messages.append(f"OK input workbook validates: {input_workbook}")
        except SyncDriveError as exc:
            blocking_issues.append(str(exc))
    else:
        blocking_issues.append(f"Input workbook not found: {input_workbook}")

    return DoctorReport(tuple(messages), tuple(blocking_issues))


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


def data_input_csvs(repo_root: Path = REPO_ROOT) -> list[Path]:
    input_dir = repo_root / "data" / "input"
    if not input_dir.exists():
        return []
    return sorted(input_dir.glob("*.csv"))


def resolve_backup_dir(
    drive_dir: Path,
    backup_dir: str | Path | None,
    timestamp: datetime | None = None,
) -> Path:
    if backup_dir is not None:
        path = Path(backup_dir).expanduser()
        return path.resolve() if path.is_absolute() else (drive_dir / path).resolve()

    backup_timestamp = (timestamp or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return (drive_dir / "backup" / backup_timestamp).resolve()


def copy_file_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def backup_operational_files(
    drive_dir: Path,
    repo_root: Path = REPO_ROOT,
    backup_dir: str | Path | None = None,
    timestamp: datetime | None = None,
) -> FileOperationResult:
    source_input = drive_dir / INPUT_WORKBOOK
    if not source_input.exists():
        raise SyncDriveError(f"Input workbook not found: {source_input}")

    destination_dir = resolve_backup_dir(drive_dir, backup_dir, timestamp)
    try:
        destination_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise SyncDriveError(
            f"Backup directory already exists: {destination_dir}"
        ) from exc

    copied: list[Path] = []
    for source in (source_input, drive_dir / VIEW_WORKBOOK):
        if source.exists():
            destination = destination_dir / source.name
            shutil.copy2(source, destination)
            copied.append(destination)

    csv_destination_dir = destination_dir / "data" / "input"
    for csv_path in data_input_csvs(repo_root):
        csv_destination_dir.mkdir(parents=True, exist_ok=True)
        destination = csv_destination_dir / csv_path.name
        shutil.copy2(csv_path, destination)
        copied.append(destination)

    return FileOperationResult(destination_dir, tuple(copied))


def restore_operational_files(
    drive_dir: Path,
    backup_dir: Path,
    repo_root: Path = REPO_ROOT,
) -> FileOperationResult:
    backup_dir = backup_dir.expanduser().resolve()
    if not backup_dir.exists() or not backup_dir.is_dir():
        raise SyncDriveError(f"Backup directory not found: {backup_dir}")

    source_input = backup_dir / INPUT_WORKBOOK
    if not source_input.exists():
        raise SyncDriveError(f"Backup is missing {INPUT_WORKBOOK}: {backup_dir}")

    restored: list[Path] = []
    for source in (source_input, backup_dir / VIEW_WORKBOOK):
        if source.exists():
            destination = drive_dir / source.name
            copy_file_atomic(source, destination)
            restored.append(destination)

    csv_source_dir = backup_dir / "data" / "input"
    if csv_source_dir.exists():
        for source in sorted(csv_source_dir.glob("*.csv")):
            destination = repo_root / "data" / "input" / source.name
            copy_file_atomic(source, destination)
            restored.append(destination)

    return FileOperationResult(backup_dir, tuple(restored))


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
        ("doctor", "Verify Drive directory, workbook schema, and conflict state"),
        ("import", "Import input.xlsx sheets into data/input/*.csv"),
        ("export", "Export data/calculated/*.csv into view.xlsx"),
        ("backup", "Snapshot Drive workbooks and data/input/*.csv"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--drive-dir",
            help=(
                f"Directory containing {INPUT_WORKBOOK} and receiving "
                f"{VIEW_WORKBOOK}; defaults to {DRIVE_DIR_ENV} or repo root."
            ),
        )

    backup_parser = subparsers.choices["backup"]
    backup_parser.add_argument(
        "--backup-dir",
        help=(
            "Destination backup directory. Relative paths resolve under the Drive "
            "directory. Defaults to backup/YYYYMMDD-HHMMSS under the Drive directory."
        ),
    )

    restore_parser = subparsers.add_parser(
        "restore", help="Restore Drive workbooks and data/input/*.csv from a backup"
    )
    restore_parser.add_argument(
        "--drive-dir",
        help=(
            f"Directory containing {INPUT_WORKBOOK} and receiving {VIEW_WORKBOOK}; "
            f"defaults to {DRIVE_DIR_ENV} or repo root."
        ),
    )
    restore_parser.add_argument(
        "--backup-dir",
        required=True,
        help="Explicit backup directory produced by the backup command.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    drive_dir = resolve_drive_dir(args.drive_dir)

    try:
        if args.command == "doctor":
            report = doctor_drive(drive_dir)
            for message in report.messages:
                print(message)
            for issue in report.blocking_issues:
                print(f"BLOCKING {issue}")
            return 0 if report.ok else 2

        if args.command == "import":
            written = import_input_workbook(drive_dir)
            for path in written:
                print(f"Imported {path}")
            return 0

        if args.command == "export":
            destination = export_view_workbook(drive_dir)
            print(f"Exported {destination}")
            return 0

        if args.command == "backup":
            result = backup_operational_files(drive_dir, backup_dir=args.backup_dir)
            print(f"Backup directory {result.directory}")
            for path in result.files:
                print(f"Backed up {path}")
            return 0

        if args.command == "restore":
            result = restore_operational_files(
                drive_dir, backup_dir=resolve_user_path(args.backup_dir)
            )
            for path in result.files:
                print(f"Restored {path}")
            return 0
    except SyncDriveError as exc:
        parser.exit(2, f"error: {exc}\n")

    parser.exit(2, f"error: unknown command {args.command}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
