from html.parser import HTMLParser
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from src.infrastructure.web import create_app


class InputValueParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "input":
            self.inputs.append({key: value or "" for key, value in attrs})


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def copy_templates(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    shutil.copytree(repo_root / "templates", tmp_path / "templates")


def test_input_get_works_without_calculated_forecast_csv() -> None:
    response = create_app().test_client().get("/input")

    assert response.status_code == 200
    assert "月次入力" in response.get_data(as_text=True)


def test_input_get_shows_suggestions_without_posted_amount_values(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    copy_templates(tmp_path)
    input_dir = tmp_path / "data" / "input"

    write_csv(
        input_dir / "income.csv",
        [
            {"month": "2026-05", "account_id": "salary", "amount": 100},
            {"month": "2026-06", "account_id": "salary", "amount": 200},
        ],
        ["month", "account_id", "amount"],
    )
    write_csv(
        input_dir / "expense.csv",
        [
            {"month": "2026-05", "method_id": "card", "amount": 30},
            {"month": "2026-06", "method_id": "card", "amount": 40},
        ],
        ["month", "method_id", "amount"],
    )
    write_csv(
        input_dir / "assets.csv",
        [
            {
                "month": "2026-05",
                "account_id": "bank",
                "asset_class": "cash",
                "balance": 400,
            },
            {
                "month": "2026-06",
                "account_id": "bank",
                "asset_class": "cash",
                "balance": 500,
            },
        ],
        ["month", "account_id", "asset_class", "balance"],
    )
    write_csv(
        tmp_path / "master" / "accounts.csv",
        [
            {"account_id": "salary", "name": "給与口座"},
            {"account_id": "bank", "name": "銀行"},
        ],
        ["account_id", "name"],
    )
    write_csv(
        tmp_path / "master" / "payment_methods.csv",
        [{"method_id": "card", "name": "カード", "settlement_day": 10}],
        ["method_id", "name", "settlement_day"],
    )

    response = create_app().test_client().get("/input")
    html = response.get_data(as_text=True)
    parser = InputValueParser()
    parser.feed(html)

    suggested_inputs = [
        input_
        for input_ in parser.inputs
        if input_.get("name")
        in {"income_amount[]", "expense_amount[]", "asset_balance[]"}
    ]
    identity_values = {
        input_.get("value")
        for input_ in parser.inputs
        if input_.get("name")
        in {"income_account[]", "expense_method[]", "asset_account[]"}
    }

    assert response.status_code == 200
    assert "給与口座" in html
    assert "カード" in html
    assert "銀行" in html
    assert [input_.get("value") for input_ in suggested_inputs] == ["", "", ""]
    assert {input_.get("placeholder") for input_ in suggested_inputs} == {
        "目安: 150",
        "目安: 35",
        "目安: 550",
    }
    assert {"salary", "card", "bank"}.issubset(identity_values)


def test_input_post_task_failure_restores_original_csvs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "data" / "input"
    calculated_dir = tmp_path / "data" / "calculated"

    original_income = [{"month": "2026-06", "account_id": "salary", "amount": 100}]
    original_expense = [{"month": "2026-06", "method_id": "card", "amount": 40}]
    original_assets = [
        {
            "month": "2026-06",
            "account_id": "bank",
            "asset_class": "cash",
            "balance": 500,
        }
    ]
    write_csv(
        input_dir / "income.csv", original_income, ["month", "account_id", "amount"]
    )
    write_csv(
        input_dir / "expense.csv", original_expense, ["month", "method_id", "amount"]
    )
    write_csv(
        input_dir / "assets.csv",
        original_assets,
        ["month", "account_id", "asset_class", "balance"],
    )
    write_csv(calculated_dir / "forecast.csv", [{"month": "2026-06"}], ["month"])

    def fail_on_export(cmd: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        if cmd == ["task", "run"]:
            write_csv(
                calculated_dir / "forecast.csv",
                [{"month": "staged-output"}],
                ["month"],
            )
            return subprocess.CompletedProcess(cmd, 0)
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr("src.infrastructure.web.subprocess.run", fail_on_export)

    response = (
        create_app()
        .test_client()
        .post(
            "/input",
            data={
                "target_month": "2026-06",
                "income_account[]": ["salary"],
                "income_amount[]": ["999"],
                "expense_method[]": ["card"],
                "expense_amount[]": ["888"],
                "asset_account[]": ["bank"],
                "asset_class[]": ["cash"],
                "asset_balance[]": ["777"],
            },
        )
    )

    assert response.status_code == 500
    assert "Recalculation failed" in response.get_data(as_text=True)
    assert pd.read_csv(input_dir / "income.csv").to_dict("records") == original_income
    assert pd.read_csv(input_dir / "expense.csv").to_dict("records") == original_expense
    assert pd.read_csv(input_dir / "assets.csv").to_dict("records") == original_assets
    assert pd.read_csv(calculated_dir / "forecast.csv").to_dict("records") == [
        {"month": "2026-06"}
    ]


def test_input_post_blank_suggested_rows_do_not_overwrite_existing_rows(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "data" / "input"

    original_income = [{"month": "2026-06", "account_id": "salary", "amount": 100}]
    original_expense = [{"month": "2026-06", "method_id": "card", "amount": 40}]
    original_assets = [
        {
            "month": "2026-06",
            "account_id": "bank",
            "asset_class": "cash",
            "balance": 500,
        }
    ]
    write_csv(
        input_dir / "income.csv", original_income, ["month", "account_id", "amount"]
    )
    write_csv(
        input_dir / "expense.csv", original_expense, ["month", "method_id", "amount"]
    )
    write_csv(
        input_dir / "assets.csv",
        original_assets,
        ["month", "account_id", "asset_class", "balance"],
    )

    calls: list[list[str]] = []

    def succeed(cmd: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("src.infrastructure.web.subprocess.run", succeed)

    response = (
        create_app()
        .test_client()
        .post(
            "/input",
            data={
                "target_month": "2026-06",
                "income_account[]": ["salary"],
                "income_amount[]": [""],
                "expense_method[]": ["card"],
                "expense_amount[]": [""],
                "asset_account[]": ["bank"],
                "asset_class[]": ["cash"],
                "asset_balance[]": [""],
            },
        )
    )

    assert response.status_code == 302
    assert calls == [["task", "run"], ["task", "export"], ["task", "forecast"]]
    assert pd.read_csv(input_dir / "income.csv").to_dict("records") == original_income
    assert pd.read_csv(input_dir / "expense.csv").to_dict("records") == original_expense
    assert pd.read_csv(input_dir / "assets.csv").to_dict("records") == original_assets


def test_input_post_success_writes_expected_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "data" / "input"

    write_csv(
        input_dir / "income.csv",
        [
            {"month": "2026-05", "account_id": "salary", "amount": 100},
            {"month": "2026-06", "account_id": "salary", "amount": 200},
        ],
        ["month", "account_id", "amount"],
    )
    write_csv(
        input_dir / "expense.csv",
        [
            {"month": "2026-05", "method_id": "card", "amount": 30},
            {"month": "2026-06", "method_id": "card", "amount": 40},
        ],
        ["month", "method_id", "amount"],
    )
    write_csv(
        input_dir / "assets.csv",
        [
            {
                "month": "2026-05",
                "account_id": "bank",
                "asset_class": "cash",
                "balance": 400,
            },
            {
                "month": "2026-06",
                "account_id": "bank",
                "asset_class": "cash",
                "balance": 500,
            },
        ],
        ["month", "account_id", "asset_class", "balance"],
    )

    calls: list[list[str]] = []

    def succeed(cmd: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("src.infrastructure.web.subprocess.run", succeed)

    response = (
        create_app()
        .test_client()
        .post(
            "/input",
            data={
                "target_month": "2026-06",
                "income_account[]": ["salary"],
                "income_amount[]": ["999"],
                "expense_method[]": ["card"],
                "expense_amount[]": ["888"],
                "asset_account[]": ["bank"],
                "asset_class[]": ["cash"],
                "asset_balance[]": ["777"],
            },
        )
    )

    assert response.status_code == 302
    assert calls == [["task", "run"], ["task", "export"], ["task", "forecast"]]
    assert pd.read_csv(input_dir / "income.csv").to_dict("records") == [
        {"month": "2026-05", "account_id": "salary", "amount": 100},
        {"month": "2026-06", "account_id": "salary", "amount": 999},
    ]
    assert pd.read_csv(input_dir / "expense.csv").to_dict("records") == [
        {"month": "2026-05", "method_id": "card", "amount": 30},
        {"month": "2026-06", "method_id": "card", "amount": 888},
    ]
    assert pd.read_csv(input_dir / "assets.csv").to_dict("records") == [
        {
            "month": "2026-05",
            "account_id": "bank",
            "asset_class": "cash",
            "balance": 400,
        },
        {
            "month": "2026-06",
            "account_id": "bank",
            "asset_class": "cash",
            "balance": 777,
        },
    ]
