"""Flask web server for HTMX-powered financial dashboard."""

import os
from flask import Flask, render_template, request

from src.use_cases.graph_service import GraphService


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.getcwd(), "templates"),
    )

    root_dir = os.getcwd()
    graph_service = GraphService(data_dir=root_dir)

    @app.route("/")
    def dashboard() -> str:
        """Render the main dashboard page."""
        return render_template("dashboard.html")

    @app.route("/graphs/net-worth")
    def net_worth_graph() -> str:
        """Return net worth chart HTML fragment."""
        months = request.args.get("months", type=int)
        return graph_service.get_net_worth_chart(months)

    @app.route("/graphs/cashflow")
    def cashflow_graph() -> str:
        """Return cash flow chart HTML fragment."""
        months = request.args.get("months", type=int)
        return graph_service.get_cashflow_chart(months)

    @app.route("/graphs/allocation")
    def allocation_graph() -> str:
        """Return asset allocation chart HTML fragment."""
        months = request.args.get("months", type=int)
        return graph_service.get_allocation_chart(months)

    @app.route("/graphs/ratios")
    def ratios_graph() -> str:
        """Return financial ratios chart HTML fragment."""
        months = request.args.get("months", type=int)
        return graph_service.get_ratios_chart(months)

    @app.route("/graphs/returns")
    def returns_graph() -> str:
        """Return investment returns chart HTML fragment."""
        months = request.args.get("months", type=int)
        return graph_service.get_returns_chart(months)

    @app.route("/graphs/fi")
    def fi_graph() -> str:
        """Return FI ratios chart HTML fragment."""
        months = request.args.get("months", type=int)
        return graph_service.get_fi_chart(months)

    return app


def main() -> None:
    """Run the development server."""
    app = create_app()
    print("Starting dashboard server at http://localhost:5000")
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
