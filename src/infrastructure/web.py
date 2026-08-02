"""Flask web server for HTMX-powered financial dashboard."""

from typing import Any
import os
import datetime
import shutil
import subprocess
import tempfile
from pathlib import Path
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, Response

from src.use_cases.graph_service import GraphService
from src.utils.months import month_end_label, month_period, next_month_end_label


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.getcwd(), "templates"),
    )

    root_dir = os.getcwd()
    input_dir = Path(root_dir) / "data" / "input"
    calculated_dir = Path(root_dir) / "data" / "calculated"
    graph_service = GraphService(data_dir=root_dir)

    CREDIT_CARD_MIN_SETTLEMENT_DAY = 1

    def warm_graph_cache() -> None:
        try:
            graph_service.warm_visible_cache()
        except Exception as exc:
            app.logger.info("Skipping graph cache warmup: %s", exc)

    warm_graph_cache()

    def get_data_path(filename: str) -> str:
        return str(input_dir / filename)

    def load_csv(filename: str) -> pd.DataFrame:
        path = get_data_path(filename)
        if not os.path.exists(path):
            return pd.DataFrame()
        return pd.read_csv(path)

    def replace_month(
        filename: str,
        target_month: str | None,
        rows: list[dict[str, Any]],
        columns: list[str],
    ) -> pd.DataFrame | None:
        if not rows:
            return None

        df = load_csv(filename)
        new_df = pd.DataFrame(rows, columns=columns)
        if df.empty:
            df = pd.DataFrame(columns=columns)
        else:
            target_period = month_period(target_month) if target_month else None
            if target_period is not None:
                df = df[pd.to_datetime(df["month"]).dt.to_period("M") != target_period]
        return pd.concat([df, new_df], ignore_index=True)

    def write_staged_inputs(
        updates: dict[str, pd.DataFrame], temp_root: Path
    ) -> Path | None:
        if not updates:
            return None

        staged_input_dir = temp_root / "input"
        if input_dir.exists():
            shutil.copytree(input_dir, staged_input_dir)
        else:
            staged_input_dir.mkdir(parents=True)

        for filename, df in updates.items():
            df.to_csv(staged_input_dir / filename, index=False)

        return staged_input_dir

    def snapshot_calculated(temp_root: Path) -> Path | None:
        if not calculated_dir.exists():
            return None
        snapshot_dir = temp_root / "calculated"
        shutil.copytree(calculated_dir, snapshot_dir)
        return snapshot_dir

    def restore_calculated(snapshot_dir: Path | None) -> None:
        if calculated_dir.exists():
            shutil.rmtree(calculated_dir)
        if snapshot_dir is not None:
            shutil.copytree(snapshot_dir, calculated_dir)

    def apply_staged_inputs(
        staged_input_dir: Path | None, temp_root: Path
    ) -> Path | None:
        if staged_input_dir is None:
            return None

        backup_input_dir = temp_root / "input.original"
        input_dir.parent.mkdir(parents=True, exist_ok=True)
        if input_dir.exists():
            input_dir.rename(backup_input_dir)
        staged_input_dir.rename(input_dir)
        return backup_input_dir

    def restore_inputs(backup_input_dir: Path | None) -> None:
        if backup_input_dir is None:
            return

        if input_dir.exists():
            shutil.rmtree(input_dir)
        backup_input_dir.rename(input_dir)

    def discard_backup_inputs(backup_input_dir: Path | None) -> None:
        if backup_input_dir is not None and backup_input_dir.exists():
            shutil.rmtree(backup_input_dir)

    def run_recalculation() -> None:
        print("Triggering recalculation...")

        print("Running Task: run...")
        subprocess.run(["task", "run"], check=True)

        print("Running Task: export...")
        subprocess.run(["task", "export"], check=True)

        print("Running Task: forecast...")
        subprocess.run(["task", "forecast"], check=True)

    @app.route("/")
    def dashboard() -> str:
        """Render the main dashboard page."""
        return render_template("dashboard.html")

    @app.route("/input", methods=["GET", "POST"])
    def input_view() -> str | Any:
        """Handle manual financial data input."""
        if request.method == "POST":
            target_month = request.form.get("target_month")

            inc_accounts = request.form.getlist("income_account[]")
            inc_amounts = request.form.getlist("income_amount[]")
            new_income = []
            for acc, amt in zip(inc_accounts, inc_amounts):
                if acc and amt:
                    new_income.append(
                        {"month": target_month, "account_id": acc, "amount": int(amt)}
                    )

            exp_methods = request.form.getlist("expense_method[]")
            exp_amounts = request.form.getlist("expense_amount[]")
            new_expenses = []
            for met, amt in zip(exp_methods, exp_amounts):
                if met and amt:
                    new_expenses.append(
                        {"month": target_month, "method_id": met, "amount": int(amt)}
                    )

            ass_accounts = request.form.getlist("asset_account[]")
            ass_classes = request.form.getlist("asset_class[]")
            ass_balances = request.form.getlist("asset_balance[]")
            new_assets = []
            for acc, cls, bal in zip(ass_accounts, ass_classes, ass_balances):
                if acc and cls and bal:
                    new_assets.append(
                        {
                            "month": target_month,
                            "account_id": acc,
                            "asset_class": cls,
                            "balance": int(bal),
                        }
                    )

            updates = {
                filename: df
                for filename, df in {
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
                        "assets.csv",
                        target_month,
                        new_assets,
                        ["month", "account_id", "asset_class", "balance"],
                    ),
                }.items()
                if df is not None
            }

            with tempfile.TemporaryDirectory(prefix="wealthaudit-input-") as temp_name:
                temp_root = Path(temp_name)
                staged_input_dir = write_staged_inputs(updates, temp_root)
                calculated_snapshot = snapshot_calculated(temp_root)
                backup_input_dir = apply_staged_inputs(staged_input_dir, temp_root)

                try:
                    run_recalculation()
                except subprocess.CalledProcessError as exc:
                    restore_inputs(backup_input_dir)
                    restore_calculated(calculated_snapshot)
                    graph_service.clear_cache()
                    return (
                        "Recalculation failed. Input CSV files were restored; "
                        f"failed command: {' '.join(exc.cmd)}",
                        500,
                    )
                else:
                    discard_backup_inputs(backup_input_dir)

            graph_service.clear_cache()
            warm_graph_cache()

            print("Recalculation complete.")

            return redirect(url_for("dashboard"))

        else:
            prefill_months = 6

            income_df = load_csv("income.csv")
            expense_df = load_csv("expense.csv")
            asset_df = load_csv("assets.csv")

            if income_df.empty:
                target_month = month_end_label(datetime.datetime.now().strftime("%Y-%m-%d"))
            else:
                last_month_str = (
                    income_df["month"].iloc[-1] or income_df["month"].iloc[-2]
                )
                target_month = next_month_end_label(last_month_str)

            months_list = (
                sorted(income_df["month"].unique())[-prefill_months:]
                if not income_df.empty
                else []
            )

            income_items = []
            accounts_path = os.path.join(root_dir, "master", "accounts.csv")
            accounts_df = (
                pd.read_csv(accounts_path)
                if os.path.exists(accounts_path)
                else pd.DataFrame()
            )

            if not income_df.empty:
                recent_income = income_df[income_df["month"].isin(months_list)]
                for acc in recent_income["account_id"].unique():
                    avg = int(
                        recent_income[recent_income["account_id"] == acc][
                            "amount"
                        ].mean()
                    )
                    name = acc
                    if not accounts_df.empty:
                        acc_row = accounts_df[accounts_df["account_id"] == acc]
                        if not acc_row.empty:
                            name = acc_row.iloc[0]["name"]
                    income_items.append(
                        {"account_id": acc, "name": name, "suggested_amount": avg}
                    )

            card_items = []
            other_expense_items = []

            methods_path = os.path.join(root_dir, "master", "payment_methods.csv")
            methods_df = (
                pd.read_csv(methods_path)
                if os.path.exists(methods_path)
                else pd.DataFrame()
            )

            if not expense_df.empty and not methods_df.empty:
                exp_months = sorted(expense_df["month"].unique())[-prefill_months:]
                recent_exp = expense_df[expense_df["month"].isin(exp_months)]

                for _, method in methods_df.iterrows():
                    met = method["method_id"]
                    name = method["name"]
                    settlement_day = method["settlement_day"]

                    met_data = recent_exp[recent_exp["method_id"] == met]
                    avg = int(met_data["amount"].mean()) if not met_data.empty else 0

                    item = {"method_id": met, "name": name, "suggested_amount": avg}

                    if settlement_day >= CREDIT_CARD_MIN_SETTLEMENT_DAY:
                        card_items.append(item)
                    else:
                        other_expense_items.append(item)

            asset_items = []
            if not asset_df.empty:
                asset_months = sorted(asset_df["month"].unique())[-prefill_months:]
                recent_assets = asset_df[asset_df["month"].isin(asset_months)]
                last_month_str = asset_df["month"].iloc[-1]

                last_assets = (
                    asset_df[asset_df["month"] == last_month_str]
                    .groupby(["account_id", "asset_class"], as_index=False)["balance"]
                    .sum()
                    .sort_values(by=["account_id", "asset_class"])
                )

                for _, row in last_assets.iterrows():
                    acc, cls = row["account_id"], row["asset_class"]
                    history = recent_assets[
                        (recent_assets["account_id"] == acc)
                        & (recent_assets["asset_class"] == cls)
                    ]
                    history_agg = history.groupby("month")["balance"].sum().sort_index()

                    if len(history_agg) >= 2:
                        values = history_agg.values
                        slope = (values[-1] - values[0]) / len(values)
                        extrapolated = max(0, int(values[-1] + slope))
                    else:
                        extrapolated = int(row["balance"])

                    name = acc
                    if not accounts_df.empty:
                        acc_row = accounts_df[accounts_df["account_id"] == acc]
                        if not acc_row.empty:
                            name = acc_row.iloc[0]["name"]

                    asset_items.append(
                        {
                            "account_id": acc,
                            "name": name,
                            "asset_class": cls,
                            "suggested_balance": extrapolated,
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

    @app.route("/graphs/net-worth")
    def net_worth_graph() -> str:
        """Return net worth chart HTML fragment."""
        months = request.args.get("months", type=int)
        forecast = request.args.get("forecast", type=int)
        return graph_service.get_net_worth_chart(months, forecast)

    @app.route("/graphs/cashflow")
    def cashflow_graph() -> str:
        """Return cash flow chart HTML fragment."""
        months = request.args.get("months", type=int)
        forecast = request.args.get("forecast", type=int)
        return graph_service.get_cashflow_chart(months, forecast)

    @app.route("/graphs/allocation")
    def allocation_graph() -> str:
        """Return asset allocation chart HTML fragment."""
        months = request.args.get("months", type=int)
        forecast = request.args.get("forecast", type=int)
        return graph_service.get_allocation_chart(months, forecast)

    @app.route("/graphs/ratios")
    def ratios_graph() -> str:
        """Return financial ratios chart HTML fragment."""
        months = request.args.get("months", type=int)
        forecast = request.args.get("forecast", type=int)
        return graph_service.get_ratios_chart(months, forecast)

    @app.route("/graphs/returns")
    def returns_graph() -> str:
        """Return investment returns chart HTML fragment."""
        months = request.args.get("months", type=int)
        forecast = request.args.get("forecast", type=int)
        return graph_service.get_returns_chart(months, forecast)

    @app.route("/graphs/fi")
    def fi_graph() -> str:
        """Return FI ratios chart HTML fragment."""
        months = request.args.get("months", type=int)
        forecast = request.args.get("forecast", type=int)
        return graph_service.get_fi_chart(months, forecast)

    @app.after_request
    def add_header(response: Response) -> Response:
        """
        Add headers to both force latest IE rendering engine or Chrome Frame,
        and also to cache the rendered page for 10 minutes.
        """
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "-1"
        return response

    return app


def main() -> None:
    """Run the development server."""
    app = create_app()
    print("Starting dashboard server at http://localhost:5000")
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
