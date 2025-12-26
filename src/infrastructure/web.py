"""Flask web server for HTMX-powered financial dashboard."""

import os
import datetime
import pandas as pd
from dateutil.relativedelta import relativedelta
from flask import Flask, render_template, request, redirect, url_for

from src.use_cases.graph_service import GraphService


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.getcwd(), "templates"),
    )

    root_dir = os.getcwd()
    graph_service = GraphService(data_dir=root_dir)

    # Configuration constants
    MA_MONTHS = 6  # Number of months for moving average / extrapolation
    CREDIT_CARD_MIN_SETTLEMENT_DAY = 1  # settlement_day >= this = credit card

    def get_data_path(filename: str) -> str:
        return os.path.join(root_dir, "data", "input", filename)

    def load_csv(filename: str) -> pd.DataFrame:
        path = get_data_path(filename)
        if not os.path.exists(path):
            return pd.DataFrame()
        return pd.read_csv(path)

    @app.route("/")
    def dashboard() -> str:
        """Render the main dashboard page."""
        return render_template("dashboard.html")

    @app.route("/input", methods=["GET", "POST"])
    def input_view() -> str:
        """Handle manual financial data input."""
        if request.method == "POST":
            # 1. Parse Form Data
            target_month = request.form.get("target_month")

            # Income
            inc_accounts = request.form.getlist("income_account[]")
            inc_amounts = request.form.getlist("income_amount[]")
            new_income = []
            for acc, amt in zip(inc_accounts, inc_amounts):
                if acc and amt:
                    new_income.append(
                        {"month": target_month, "account_id": acc, "amount": int(amt)}
                    )

            # Expense
            exp_methods = request.form.getlist("expense_method[]")
            exp_amounts = request.form.getlist("expense_amount[]")
            new_expenses = []
            for met, amt in zip(exp_methods, exp_amounts):
                if met and amt:
                    new_expenses.append(
                        {"month": target_month, "method_id": met, "amount": int(amt)}
                    )

            # Assets
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

            # 2. Save
            if new_income:
                df = load_csv("income.csv")
                new_df = pd.DataFrame(new_income)
                # Ensure correct columns if file empty
                if df.empty:
                    df = pd.DataFrame(columns=["month", "account_id", "amount"])
                pd.concat([df, new_df]).to_csv(get_data_path("income.csv"), index=False)

            if new_expenses:
                df = load_csv("expense.csv")
                new_df = pd.DataFrame(new_expenses)
                if df.empty:
                    df = pd.DataFrame(columns=["month", "method_id", "amount"])
                pd.concat([df, new_df]).to_csv(
                    get_data_path("expense.csv"), index=False
                )

            if new_assets:
                df = load_csv("assets.csv")
                new_df = pd.DataFrame(new_assets)
                if df.empty:
                    df = pd.DataFrame(
                        columns=["month", "account_id", "asset_class", "balance"]
                    )
                pd.concat([df, new_df]).to_csv(get_data_path("assets.csv"), index=False)

            return redirect(url_for("dashboard"))

        else:
            # --- GET: Pre-fill using 6-month moving average ---
            income_df = load_csv("income.csv")
            expense_df = load_csv("expense.csv")
            asset_df = load_csv("assets.csv")

            # Determine Target Month
            if income_df.empty:
                target_month = datetime.datetime.now().strftime("%Y-%m")
            else:
                last_month_str = (
                    income_df["month"].iloc[-1] or income_df["month"].iloc[-2]
                )
                last_date = datetime.datetime.strptime(last_month_str, "%Y-%m")
                target_month = (last_date + relativedelta(months=1)).strftime("%Y-%m")

            # Get last 6 months for averaging
            months_list = (
                sorted(income_df["month"].unique())[-MA_MONTHS:]
                if not income_df.empty
                else []
            )

            # Pre-fill Income (6MA) - load names from master
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
                    # Get account name from master
                    name = acc
                    if not accounts_df.empty:
                        acc_row = accounts_df[accounts_df["account_id"] == acc]
                        if not acc_row.empty:
                            name = acc_row.iloc[0]["name"]
                    income_items.append(
                        {"account_id": acc, "name": name, "amount": avg}
                    )

            # Pre-fill Expenses (6MA) - load from master
            card_items = []
            other_expense_items = []

            # Load payment methods master
            methods_path = os.path.join(root_dir, "master", "payment_methods.csv")
            methods_df = (
                pd.read_csv(methods_path)
                if os.path.exists(methods_path)
                else pd.DataFrame()
            )

            if not expense_df.empty and not methods_df.empty:
                exp_months = sorted(expense_df["month"].unique())[-MA_MONTHS:]
                recent_exp = expense_df[expense_df["month"].isin(exp_months)]

                for _, method in methods_df.iterrows():
                    met = method["method_id"]
                    name = method["name"]
                    settlement_day = method["settlement_day"]

                    # Calculate 6MA
                    met_data = recent_exp[recent_exp["method_id"] == met]
                    avg = int(met_data["amount"].mean()) if not met_data.empty else 0

                    item = {"method_id": met, "name": name, "amount": avg}

                    # Credit cards have settlement_day >= threshold
                    if settlement_day >= CREDIT_CARD_MIN_SETTLEMENT_DAY:
                        card_items.append(item)
                    else:
                        other_expense_items.append(item)

            # Pre-fill Assets (linear extrapolation from 6 months)
            asset_items = []
            if not asset_df.empty:
                asset_months = sorted(asset_df["month"].unique())[-MA_MONTHS:]
                recent_assets = asset_df[asset_df["month"].isin(asset_months)]
                last_month_str = asset_df["month"].iloc[-1]

                # Aggregate duplicates: group by account_id + asset_class and sum
                last_assets = (
                    asset_df[asset_df["month"] == last_month_str]
                    .groupby(["account_id", "asset_class"], as_index=False)["balance"]
                    .sum()
                    .sort_values(by=["account_id", "asset_class"])
                )

                for _, row in last_assets.iterrows():
                    acc, cls = row["account_id"], row["asset_class"]
                    # Get history for this account/class (aggregated per month)
                    history = recent_assets[
                        (recent_assets["account_id"] == acc)
                        & (recent_assets["asset_class"] == cls)
                    ]
                    history_agg = history.groupby("month")["balance"].sum().sort_index()

                    if len(history_agg) >= 2:
                        # Linear extrapolation: y = last + slope
                        values = history_agg.values
                        slope = (values[-1] - values[0]) / len(values)
                        extrapolated = max(0, int(values[-1] + slope))  # No negative
                    else:
                        extrapolated = int(row["balance"])

                    # Get account name from master
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
                            "balance": extrapolated,
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

    return app


def main() -> None:
    """Run the development server."""
    app = create_app()
    print("Starting dashboard server at http://localhost:5000")
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
