from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.use_cases.graph_service import GraphService, last_completed_month, total_wealth_flow

FORECAST_FILE = Path("data/calculated/forecast.csv")
PARAMETERS_FILE = Path("data/calculated/forecast_parameters.csv")
AUDIT_FILE = Path("data/calculated/recalculation_diff.csv")
MAX_LIMIT = 120


def _clean_value(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _clean_row(row: pd.Series, fields: Iterable[str]) -> tuple[dict[str, object], dict[str, str]]:
    values: dict[str, object] = {}
    null_reasons: dict[str, str] = {}
    for field in fields:
        if field not in row.index:
            values[field] = None
            null_reasons[field] = "column_not_materialized"
            continue
        value = _clean_value(row[field])
        values[field] = value
        if value is None:
            null_reasons[field] = "value_missing"
    return values, null_reasons


class FinancialReadModel:
    """Read-only adapter over WealthAudit's calculated local dataset.

    The adapter never writes operational files and never exposes absolute private paths.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.graphs = GraphService(str(self.repo_root))

    def _path(self, relative: Path) -> Path:
        return self.repo_root / relative

    def _forecast_path(self) -> Path:
        return self._path(FORECAST_FILE)

    def _load_forecast(self) -> pd.DataFrame:
        path = self._forecast_path()
        if not path.is_file():
            raise FileNotFoundError("calculated_forecast_not_materialized")
        frame = pd.read_csv(path)
        if "month" not in frame.columns or "is_forecast" not in frame.columns:
            raise ValueError("forecast.csv requires month and is_forecast columns")
        frame = frame.copy()
        frame["month"] = frame["month"].astype(str)
        frame["is_forecast"] = frame["is_forecast"].astype(bool)
        return frame.sort_values("month").reset_index(drop=True)

    def _artifact_meta(self, relative: Path = FORECAST_FILE) -> dict[str, object]:
        path = self._path(relative)
        if not path.is_file():
            return {
                "input_source": str(relative).replace("\\", "/"),
                "input_hash": None,
                "generated_at": None,
                "null_reason": "artifact_not_materialized",
            }
        raw = path.read_bytes()
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(microsecond=0)
        return {
            "input_source": str(relative).replace("\\", "/"),
            "input_hash": hashlib.sha256(raw).hexdigest(),
            "generated_at": modified.isoformat().replace("+00:00", "Z"),
            "null_reason": None,
        }

    @staticmethod
    def _actual_or_forecast(row: pd.Series) -> str:
        return "forecast" if bool(row["is_forecast"]) else "actual"

    def _row_payload(self, row: pd.Series, fields: Iterable[str], *, derivation: str) -> dict[str, object]:
        values, null_reasons = _clean_row(row, fields)
        return {
            "schema_version": "wealthaudit.financial-row.v1",
            "period": str(row["month"]),
            "actual_or_forecast": self._actual_or_forecast(row),
            "values": values,
            "null_reasons": null_reasons,
            "derivation_method": derivation,
            "provenance": self._artifact_meta(),
        }

    def _select_period(self, period: str | None, *, forecast: bool | None = None) -> pd.Series | None:
        frame = self._load_forecast()
        if forecast is not None:
            frame = frame[frame["is_forecast"] == forecast]
        if period is not None:
            frame = frame[frame["month"] == period]
        if frame.empty:
            return None
        return frame.iloc[-1]

    def financial_snapshot(self, period: str | None = None) -> dict[str, object]:
        row = self._select_period(period, forecast=False if period is None else None)
        if row is None:
            return {"available": False, "null_reason": "period_not_materialized", "period": period}
        fields = (
            "liquid_assets",
            "risk_assets",
            "pension_assets",
            "after_tax_income",
            "expenditure",
            "net_savings",
            "investment_gain_loss",
            "monthly_return",
            "benchmark_return",
            "monthly_alpha",
            "fi_ratio_12m",
            "fi_ratio_48m",
            "fi_ratio_next_12m",
        )
        payload = self._row_payload(row, fields, derivation="materialized forecast.csv read model")
        assets = [payload["values"].get(name) for name in ("liquid_assets", "risk_assets", "pension_assets")]  # type: ignore[union-attr]
        payload["net_worth"] = sum(float(value) for value in assets if value is not None)
        return {"available": True, **payload}

    def balance_sheet(self, period: str | None = None) -> dict[str, object]:
        row = self._select_period(period, forecast=False if period is None else None)
        if row is None:
            return {"available": False, "null_reason": "period_not_materialized", "period": period}
        return {
            "available": True,
            **self._row_payload(
                row,
                ("liquid_assets", "risk_assets", "pension_assets", "total_financial_assets"),
                derivation="scripts/forecast.py calculated balance-sheet projection",
            ),
        }

    def cash_flow(self, period: str | None = None) -> dict[str, object]:
        row = self._select_period(period, forecast=False if period is None else None)
        if row is None:
            return {"available": False, "null_reason": "period_not_materialized", "period": period}
        values = ("after_tax_income", "expenditure", "net_savings", "asset_contribution", "net_worth_contribution", "investment_gain_loss")
        payload = self._row_payload(row, values, derivation="materialized cash-flow formulas shared with dashboard")
        one = pd.DataFrame([row])
        try:
            payload["values"]["total_wealth_flow"] = _clean_value(total_wealth_flow(one).iloc[-1])  # type: ignore[index]
        except KeyError:
            payload["values"]["total_wealth_flow"] = None  # type: ignore[index]
            payload["null_reasons"]["total_wealth_flow"] = "required_flow_column_missing"  # type: ignore[index]
        return {"available": True, **payload}

    def asset_allocation(self, period: str | None = None) -> dict[str, object]:
        row = self._select_period(period, forecast=False if period is None else None)
        if row is None:
            return {"available": False, "null_reason": "period_not_materialized", "period": period}
        table = self.graphs._prepare_table_frame("allocation", pd.DataFrame([row]))
        prepared = table.iloc[-1]
        return {
            "available": True,
            **self._row_payload(
                prepared,
                (
                    "liquid_assets",
                    "risk_assets",
                    "pension_assets",
                    "liquid_assets_ratio",
                    "risk_assets_ratio",
                    "pension_assets_ratio",
                ),
                derivation="GraphService allocation table calculation",
            ),
        }

    def investment_returns(self, period: str | None = None) -> dict[str, object]:
        row = self._select_period(period, forecast=False if period is None else None)
        if row is None:
            return {"available": False, "null_reason": "period_not_materialized", "period": period}
        return {
            "available": True,
            **self._row_payload(
                row,
                ("raw_monthly_return", "monthly_return", "raw_benchmark_return", "benchmark_return", "monthly_alpha"),
                derivation="scripts/forecast.py calculate_metrics_vectorized",
            ),
        }

    def fi_metrics(self, period: str | None = None) -> dict[str, object]:
        row = self._select_period(period, forecast=False if period is None else None)
        if row is None:
            return {"available": False, "null_reason": "period_not_materialized", "period": period}
        return {
            "available": True,
            **self._row_payload(
                row,
                ("savings_rate", "risk_asset_ratio", "fi_ratio_12m", "fi_ratio_48m", "fi_ratio_next_12m"),
                derivation="scripts/forecast.py calculate_metrics_vectorized",
            ),
        }

    def forecast(self, months: int = 12) -> dict[str, object]:
        if not 1 <= months <= MAX_LIMIT:
            raise ValueError(f"months must be between 1 and {MAX_LIMIT}")
        frame = self._load_forecast()
        future = frame[frame["is_forecast"]].head(months)
        fields = (
            "liquid_assets",
            "risk_assets",
            "pension_assets",
            "after_tax_income",
            "expenditure",
            "net_savings",
            "investment_gain_loss",
            "monthly_return",
            "fi_ratio_next_12m",
        )
        parameter_path = self._path(PARAMETERS_FILE)
        assumptions = []
        assumptions_meta = self._artifact_meta(PARAMETERS_FILE)
        if parameter_path.is_file():
            assumptions = pd.read_csv(parameter_path).replace({float("nan"): None}).to_dict(orient="records")
        return {
            "schema_version": "wealthaudit.forecast.v1",
            "actual_or_forecast": "forecast",
            "count": len(future),
            "items": [self._row_payload(row, fields, derivation="scripts/forecast.py deterministic forecast") for _, row in future.iterrows()],
            "assumptions": assumptions,
            "assumptions_provenance": assumptions_meta,
        }

    def warnings(self) -> dict[str, object]:
        try:
            frame = self._load_forecast()
        except (FileNotFoundError, ValueError) as exc:
            return {
                "schema_version": "wealthaudit.warnings.v1",
                "status": "unavailable",
                "warnings": [str(exc)],
                "null_reason": "calculated_dataset_unavailable",
            }
        warnings: list[dict[str, object]] = []
        if frame["month"].duplicated().any():
            warnings.append({"code": "duplicate_month", "severity": "error"})
        actual = frame[~frame["is_forecast"]]
        if actual.empty:
            warnings.append({"code": "actual_rows_missing", "severity": "error"})
        else:
            latest = str(actual.iloc[-1]["month"])
            cutoff = last_completed_month()
            if latest < cutoff:
                warnings.append({"code": "actual_data_stale", "severity": "warning", "latest_period": latest, "expected_through": cutoff})
            if actual.iloc[-1].isna().any():
                warnings.append({"code": "latest_actual_contains_null", "severity": "warning"})
        return {
            "schema_version": "wealthaudit.warnings.v1",
            "status": "ok" if not warnings else "warning",
            "warnings": warnings,
            "null_reason": None,
        }

    def data_freshness(self) -> dict[str, object]:
        meta = self._artifact_meta()
        if meta["null_reason"] is not None:
            return {"available": False, **meta}
        frame = self._load_forecast()
        actual = frame[~frame["is_forecast"]]
        latest = None if actual.empty else str(actual.iloc[-1]["month"])
        cutoff = last_completed_month()
        return {
            "available": True,
            "latest_actual_period": latest,
            "expected_through": cutoff,
            "stale": latest is None or latest < cutoff,
            "edinetdb_mode": "not_applicable",
            **meta,
        }

    def audit_diff(self, limit: int = 100) -> dict[str, object]:
        if not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        path = self._path(AUDIT_FILE)
        meta = self._artifact_meta(AUDIT_FILE)
        if not path.is_file():
            return {
                "schema_version": "wealthaudit.audit-diff.v1",
                "available": False,
                "null_reason": "recalculation_diff_not_materialized",
                "items": [],
                "provenance": meta,
            }
        frame = pd.read_csv(path).head(limit)
        items = []
        for _, row in frame.iterrows():
            items.append({key: _clean_value(value) for key, value in row.items()})
        return {
            "schema_version": "wealthaudit.audit-diff.v1",
            "available": True,
            "count": len(items),
            "items": items,
            "provenance": meta,
        }
