from pathlib import Path

import pandas as pd
import pytest

from scripts.sync_drive import (
    SyncDriveError,
    export_view_workbook,
    import_input_workbook,
    resolve_drive_dir,
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
