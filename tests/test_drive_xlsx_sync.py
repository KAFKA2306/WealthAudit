from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from scripts.sync_drive import (
    SyncDriveError,
    backup_operational_files,
    detect_conflict_files,
    doctor_drive,
    export_view_workbook,
    import_input_workbook,
    resolve_drive_dir,
    restore_operational_files,
)


def write_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def input_sheets() -> dict[str, pd.DataFrame]:
    return {
        "income": pd.DataFrame(
            [{"month": "2026-01", "account_id": "bank", "amount": 300000}]
        ),
        "expense": pd.DataFrame(
            [{"month": "2026-01", "method_id": "card", "amount": 120000}]
        ),
        "assets": pd.DataFrame(
            [
                {
                    "month": "2026-01",
                    "account_id": "bank",
                    "asset_class": "cash",
                    "balance": 1000000,
                }
            ]
        ),
        "market": pd.DataFrame(
            [{"month": "2026-01", "usd_jpy": 150, "eur_jpy": 160, "sp500": 5000}]
        ),
    }


def test_import_input_workbook_writes_required_csvs(tmp_path: Path) -> None:
    drive_dir = tmp_path / "drive"
    repo_root = tmp_path / "repo"
    write_workbook(drive_dir / "input.xlsx", input_sheets())

    written = import_input_workbook(drive_dir, repo_root=repo_root)

    assert [path.name for path in written] == [
        "income.csv",
        "expense.csv",
        "assets.csv",
        "market.csv",
    ]
    assert (repo_root / "data" / "input" / "income.csv").exists()
    income = pd.read_csv(repo_root / "data" / "input" / "income.csv")
    assert income.to_dict("records") == [
        {"month": "2026-01", "account_id": "bank", "amount": 300000}
    ]


def test_import_input_workbook_fails_before_writing_on_missing_columns(
    tmp_path: Path,
) -> None:
    drive_dir = tmp_path / "drive"
    repo_root = tmp_path / "repo"
    sheets = input_sheets()
    sheets["assets"] = sheets["assets"].drop(columns=["balance"])
    write_workbook(drive_dir / "input.xlsx", sheets)

    with pytest.raises(SyncDriveError, match="assets: missing columns balance"):
        import_input_workbook(drive_dir, repo_root=repo_root)

    assert not (repo_root / "data" / "input").exists()


def test_import_input_workbook_validates_required_sheets(tmp_path: Path) -> None:
    drive_dir = tmp_path / "drive"
    repo_root = tmp_path / "repo"
    sheets = input_sheets()
    del sheets["market"]
    write_workbook(drive_dir / "input.xlsx", sheets)

    with pytest.raises(SyncDriveError, match="missing required sheets: market"):
        import_input_workbook(drive_dir, repo_root=repo_root)


def test_doctor_drive_accepts_valid_local_drive_dir(tmp_path: Path) -> None:
    drive_dir = tmp_path / "drive"
    write_workbook(drive_dir / "input.xlsx", input_sheets())

    report = doctor_drive(drive_dir)

    assert report.ok
    assert not report.blocking_issues
    assert any("input workbook validates" in message for message in report.messages)


def test_doctor_drive_blocks_missing_input_workbook(tmp_path: Path) -> None:
    drive_dir = tmp_path / "drive"
    drive_dir.mkdir()

    report = doctor_drive(drive_dir)

    assert not report.ok
    assert report.blocking_issues == (
        f"Input workbook not found: {drive_dir / 'input.xlsx'}",
    )


def test_doctor_drive_blocks_conflict_and_temp_files(tmp_path: Path) -> None:
    drive_dir = tmp_path / "drive"
    write_workbook(drive_dir / "input.xlsx", input_sheets())
    (drive_dir / "input (Conflicted copy).xlsx").touch()
    (drive_dir / "~$input.xlsx").touch()
    (drive_dir / "upload.tmp").touch()

    report = doctor_drive(drive_dir)

    assert not report.ok
    assert list(detect_conflict_files(drive_dir)) == [
        drive_dir / "input (Conflicted copy).xlsx",
        drive_dir / "upload.tmp",
        drive_dir / "~$input.xlsx",
    ]
    assert (
        sum("Conflict/temp file present" in issue for issue in report.blocking_issues)
        == 3
    )


def test_export_view_workbook_writes_existing_calculated_csvs_in_order(
    tmp_path: Path,
) -> None:
    drive_dir = tmp_path / "drive"
    calculated_dir = tmp_path / "repo" / "data" / "calculated"
    calculated_dir.mkdir(parents=True)
    for name in (
        "forecast",
        "metrics",
        "balance_sheet",
        "cashflow",
        "normalized",
        "forecast_annual",
    ):
        pd.DataFrame([{"month": "2026-01", "value": name}]).to_csv(
            calculated_dir / f"{name}.csv", index=False
        )

    destination = export_view_workbook(drive_dir, repo_root=tmp_path / "repo")

    assert destination == drive_dir / "view.xlsx"
    workbook = pd.ExcelFile(destination)
    assert workbook.sheet_names == [
        "cashflow",
        "balance_sheet",
        "metrics",
        "normalized",
        "forecast",
        "forecast_annual",
    ]
    forecast = pd.read_excel(destination, sheet_name="forecast", engine="openpyxl")
    assert forecast.to_dict("records") == [{"month": "2026-01", "value": "forecast"}]


def test_export_view_workbook_fails_when_no_calculated_csvs(
    tmp_path: Path,
) -> None:
    with pytest.raises(SyncDriveError, match="No calculated CSVs found"):
        export_view_workbook(tmp_path / "drive", repo_root=tmp_path / "repo")


def test_resolve_drive_dir_uses_env_before_repo_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEALTHAUDIT_DRIVE_DIR", str(tmp_path))

    assert resolve_drive_dir(None) == tmp_path.resolve()


def test_backup_operational_files_snapshots_workbooks_and_input_csvs(
    tmp_path: Path,
) -> None:
    drive_dir = tmp_path / "drive"
    repo_root = tmp_path / "repo"
    input_dir = repo_root / "data" / "input"
    input_dir.mkdir(parents=True)
    write_workbook(drive_dir / "input.xlsx", input_sheets())
    write_workbook(
        drive_dir / "view.xlsx",
        {"metrics": pd.DataFrame([{"month": "2026-01", "value": 1}])},
    )
    pd.DataFrame([{"month": "2026-01", "amount": 300000}]).to_csv(
        input_dir / "income.csv", index=False
    )

    result = backup_operational_files(
        drive_dir,
        repo_root=repo_root,
        timestamp=datetime(2026, 7, 10, 12, 34, 56),
    )

    assert result.directory == (drive_dir / "backup" / "20260710-123456").resolve()
    assert sorted(path.relative_to(result.directory) for path in result.files) == [
        Path("data/input/income.csv"),
        Path("input.xlsx"),
        Path("view.xlsx"),
    ]
    assert (result.directory / "input.xlsx").exists()
    assert (result.directory / "view.xlsx").exists()
    assert (result.directory / "data" / "input" / "income.csv").exists()


def test_backup_operational_files_supports_configurable_relative_backup_dir(
    tmp_path: Path,
) -> None:
    drive_dir = tmp_path / "drive"
    write_workbook(drive_dir / "input.xlsx", input_sheets())

    result = backup_operational_files(drive_dir, backup_dir="custom/one")

    assert result.directory == (drive_dir / "custom" / "one").resolve()
    assert (result.directory / "input.xlsx").exists()


def test_backup_operational_files_fails_when_input_is_missing(tmp_path: Path) -> None:
    with pytest.raises(SyncDriveError, match="Input workbook not found"):
        backup_operational_files(tmp_path / "drive", repo_root=tmp_path / "repo")


def test_restore_operational_files_restores_backup_contents(tmp_path: Path) -> None:
    drive_dir = tmp_path / "drive"
    repo_root = tmp_path / "repo"
    backup_dir = tmp_path / "backup"
    write_workbook(backup_dir / "input.xlsx", input_sheets())
    write_workbook(
        backup_dir / "view.xlsx",
        {"metrics": pd.DataFrame([{"month": "2026-01", "value": "restored"}])},
    )
    csv_dir = backup_dir / "data" / "input"
    csv_dir.mkdir(parents=True)
    pd.DataFrame([{"month": "2026-01", "amount": 1}]).to_csv(
        csv_dir / "income.csv", index=False
    )

    result = restore_operational_files(drive_dir, backup_dir, repo_root=repo_root)

    assert result.directory == backup_dir.resolve()
    assert sorted(path.name for path in result.files) == [
        "income.csv",
        "input.xlsx",
        "view.xlsx",
    ]
    assert (drive_dir / "input.xlsx").exists()
    assert (drive_dir / "view.xlsx").exists()
    income = pd.read_csv(repo_root / "data" / "input" / "income.csv")
    assert income.to_dict("records") == [{"month": "2026-01", "amount": 1}]


def test_restore_operational_files_requires_explicit_valid_backup_dir(
    tmp_path: Path,
) -> None:
    with pytest.raises(SyncDriveError, match="Backup directory not found"):
        restore_operational_files(tmp_path / "drive", tmp_path / "missing")
