"""Flask web server for the WealthAudit dashboard and monthly input."""

from __future__ import annotations

import datetime
import os
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from dateutil.relativedelta import relativedelta  # type: ignore
from flask import Flask, Response, redirect, render_template, request, url_for

from src.infrastructure.monthly_close import FilesystemMonthlyClosePort
from src.use_cases.graph_service import GraphService
from src.use_cases.monthly_close import MonthlyCloseError, MonthlyCloseWorkflow


def create_app() -> Flask:
    app = Flask(__name__, template_folder=os.path.join(os.getcwd(), "templates"))
    root_dir = Path(os.getcwd())
    input_dir = root_dir / "data" / "input"
    graph_service = GraphService(data_dir=str(root_dir))

    def warm_graph_cache() -> None:
        try:
            graph_service.warm_visible_cache()
        except Exception as exc:  # data may not exist during first setup
            app.logger.info("Skipping graph cache warmup: %s", exc)

    warm_graph_cache()

    def load_csv(filename: str) -> pd.DataFrame:
        path = input_dir / filename
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    def replace_month(
        filename: str,
        target_month: str | None,
        rows: list[dict[str, Any]],
        columns: list[str],
    ) -> pd.DataFrame | None:
        if not rows:
            return None
        current = load_csv(filename)
        new_frame = pd.DataFrame(rows, columns=columns)
        if current.empty:
            current = pd.DataFrame(columns=columns)
        else:
            current = current[current["month"] != target_month]
        return pd.concat([current, new_frame], ignore_index=True)

    def run_task(command: tuple[str, ...], cwd: Path) -> None:
        subprocess.run(list(command), cwd=cwd, check=True)

    def accounts_frame() -> pd.DataFrame:
        path = root_dir / "master" / "accounts.csv"
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    @app.route("/")
    def dashboard() -> str:
        return render_template("dashboard.html")

    @app.route("/input", methods=["GET", "POST"])
    def input_view() -> str | Any:
        accounts = accounts_frame()
        if request.method == "POST":
            target_month = request.form.get("target_month")
            if not target_month:
                return "target_month is required", 400

            new_income = [
                {"month": target_month, "account_id": account, "amount": int(amount)}
                for account, amount in zip(
                    request.form.getlist("income_account[]"),
                    request.form.getlist("income_amount[]"),
                )
                if account and amount
            ]
            new_expenses = [
                {"month": target_month, "method_id": method, "amount": int(amount)}
                for method, amount in zip(
                    request.form.getlist("expense_method[]"),
                    request.form.getlist("expense_amount[]"),
                )
                if method and amount
            ]

            asset_accounts = request.form.getlist("asset_account[]")
            asset_classes = request.form.getlist("asset_class[]")
            asset_balances = request.form.getlist("asset_balance[]")
            asset_currencies = request.form.getlist("asset_currency[]")
            asset_currencies += [""] * (len(asset_accounts) - len(asset_currencies))
            account_currency = (
                dict(zip(accounts["account_id"], accounts["currency"]))
                if not accounts.empty and "currency" in accounts
                else {}
            )
            existing_assets = load_csv("assets.csv")
            balance_column = (
                "native_balance"
                if "native_balance" in existing_assets.columns
                else "balance"
            )
            include_currency = "native_currency" in existing_assets.columns
            new_assets: list[dict[str, Any]] = []
            for account, asset_class, balance, currency in zip(
                asset_accounts, asset_classes, asset_balances, asset_currencies
            ):
                if not (account and asset_class and balance):
                    continue
                configured_currency = str(account_currency.get(account, ""))
                resolved_currency = currency.strip() or (
                    configured_currency if configured_currency != "multi" else ""
                )
                if configured_currency == "multi" and not resolved_currency:
                    return (
                        f"native_currency is required for multi-currency account {account}",
                        400,
                    )
                row: dict[str, Any] = {
                    "month": target_month,
                    "account_id": account,
                    "asset_class": asset_class,
                    balance_column: float(balance),
                }
                if include_currency or configured_currency == "multi" or currency.strip():
                    row["native_currency"] = resolved_currency
                    include_currency = True
                new_assets.append(row)

            asset_columns = ["month", "account_id", "asset_class", balance_column]
            if include_currency:
                asset_columns.append("native_currency")
            updates = {
                filename: frame
                for filename, frame in {
                    "income.csv": replace_month(
                        "income.csv",
                        target_month,
                        new_income,
                        ["month", "account_id", "amount"],
                    ),
                    "expense.csv": replace_month(
                        "expense.csv",
                        target_month,
                        new_expenses,
                        ["month", "method_id", "amount"],
                    ),
                    "assets.csv": replace_month(
                        "assets.csv", target_month, new_assets, asset_columns
                    ),
                }.items()
                if frame is not None
            }

            try:
                MonthlyCloseWorkflow().execute(
                    FilesystemMonthlyClosePort(
                        repo_root=root_dir,
                        month=target_month,
                        updates=updates,
                        command_runner=run_task,
                    )
                )
            except MonthlyCloseError as exc:
                graph_service.clear_cache()
                app.logger.error("Monthly close failed: %s", exc)
                return f"Recalculation failed. Monthly close was rolled back: {exc}", 500

            graph_service.clear_cache()
            warm_graph_cache()
            return redirect(url_for("dashboard"))

        income = load_csv("income.csv")
        expense = load_csv("expense.csv")
        assets = load_csv("assets.csv")
        if income.empty:
            target_month = datetime.datetime.now().strftime("%Y-%m")
        else:
            last_date = datetime.datetime.strptime(str(income["month"].iloc[-1]), "%Y-%m")
            target_month = (last_date + relativedelta(months=1)).strftime("%Y-%m")

        account_names = (
            dict(zip(accounts["account_id"], accounts["name"]))
            if not accounts.empty
            else {}
        )
        account_currencies = (
            dict(zip(accounts["account_id"], accounts["currency"]))
            if not accounts.empty and "currency" in accounts
            else {}
        )
        recent_months = sorted(income["month"].unique())[-6:] if not income.empty else []
        recent_income = income[income["month"].isin(recent_months)] if recent_months else income
        income_items = (
            [
                {
                    "account_id": account,
                    "name": account_names.get(account, account),
                    "suggested_amount": int(group["amount"].mean()),
                }
                for account, group in recent_income.groupby("account_id")
            ]
            if not recent_income.empty
            else []
        )

        methods_path = root_dir / "master" / "payment_methods.csv"
        methods = pd.read_csv(methods_path) if methods_path.exists() else pd.DataFrame()
        card_items: list[dict[str, Any]] = []
        other_expense_items: list[dict[str, Any]] = []
        if not methods.empty:
            recent_expense_months = (
                sorted(expense["month"].unique())[-6:] if not expense.empty else []
            )
            recent_expense = (
                expense[expense["month"].isin(recent_expense_months)]
                if recent_expense_months
                else expense
            )
            for _, method in methods.iterrows():
                values = (
                    recent_expense[
                        recent_expense["method_id"] == method["method_id"]
                    ]
                    if "method_id" in recent_expense.columns
                    else pd.DataFrame(columns=["amount"])
                )
                item = {
                    "method_id": method["method_id"],
                    "name": method["name"],
                    "suggested_amount": int(values["amount"].mean())
                    if not values.empty
                    else 0,
                }
                settlement_day = int(method.get("settlement_day", 0) or 0)
                (card_items if settlement_day >= 1 else other_expense_items).append(item)

        asset_items: list[dict[str, Any]] = []
        if not assets.empty:
            balance_column = "native_balance" if "native_balance" in assets else "balance"
            last_month = str(assets["month"].max())
            latest_assets = assets[assets["month"] == last_month]
            group_columns = ["account_id", "asset_class"]
            if "native_currency" in latest_assets:
                group_columns.append("native_currency")
            latest_assets = (
                latest_assets.groupby(group_columns, dropna=False)[[balance_column]]
                .sum()
                .reset_index()
            )
            recent_asset_months = sorted(assets["month"].unique())[-6:]
            recent_assets = assets[assets["month"].isin(recent_asset_months)]
            for _, asset_row in latest_assets.iterrows():
                account_id = str(asset_row["account_id"])
                row_currency = asset_row.get("native_currency", "")
                currency = (
                    str(row_currency)
                    if pd.notna(row_currency) and str(row_currency)
                    else str(account_currencies.get(account_id, ""))
                )
                history = recent_assets[
                    (recent_assets["account_id"] == account_id)
                    & (recent_assets["asset_class"] == asset_row["asset_class"])
                ]
                if "native_currency" in history and currency and currency != "multi":
                    history = history[
                        history["native_currency"].fillna(currency).astype(str)
                        == currency
                    ]
                history_by_month = (
                    history.groupby("month")[balance_column].sum().sort_index()
                )
                if len(history_by_month) >= 2:
                    values = history_by_month.to_numpy(dtype=float)
                    slope = (values[-1] - values[0]) / len(values)
                    suggested = max(0.0, values[-1] + slope)
                else:
                    suggested = float(asset_row[balance_column])
                asset_items.append(
                    {
                        "account_id": account_id,
                        "name": account_names.get(account_id, account_id),
                        "asset_class": asset_row["asset_class"],
                        "native_currency": "" if currency == "multi" else currency,
                        "suggested_balance": int(suggested)
                        if suggested.is_integer()
                        else suggested,
                    }
                )

        return render_template(
            "input.html",
            target_month=target_month,
            income_items=income_items,
            card_items=card_items,
            other_expense_items=other_expense_items,
            asset_items=asset_items,
        )

    graph_routes = {
        "net-worth": graph_service.get_net_worth_chart,
        "cashflow": graph_service.get_cashflow_chart,
        "allocation": graph_service.get_allocation_chart,
        "ratios": graph_service.get_ratios_chart,
        "returns": graph_service.get_returns_chart,
        "fi": graph_service.get_fi_chart,
    }
    for route_name, builder in graph_routes.items():
        app.add_url_rule(
            f"/graphs/{route_name}",
            endpoint=f"graph_{route_name}",
            view_func=lambda builder=builder: builder(
                request.args.get("months", type=int),
                request.args.get("forecast", type=int),
            ),
        )

    @app.after_request
    def add_header(response: Response) -> Response:
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "-1"
        return response

    return app


def main() -> None:
    create_app().run(debug=True, port=5000)


if __name__ == "__main__":
    main()
