from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pandas as pd

from src.infrastructure.monthly_close import FilesystemMonthlyClosePort
from src.use_cases.monthly_close import MonthlyCloseResult, MonthlyCloseWorkflow
from src.use_cases.source_adapter import (
    REQUIRED_FIELDS,
    AdapterResult,
    SourceAdapter,
    write_provenance,
)


def adapter_result_to_monthly_updates(
    result: AdapterResult,
) -> dict[str, pd.DataFrame]:
    """Convert validated canonical adapter tables to the monthly-close input boundary."""

    updates: dict[str, pd.DataFrame] = {}
    for table, required in REQUIRED_FIELDS.items():
        rows = result.tables[table]
        if rows:
            frame = pd.DataFrame.from_records(rows)
        else:
            frame = pd.DataFrame(columns=sorted(required))
        updates[f"{table}.csv"] = frame
    return updates


def execute_source_monthly_close(
    adapter: SourceAdapter,
    repo_root: Path,
    target_month: str,
    *,
    known_accounts: set[str],
    known_payment_methods: set[str],
    fetched_at: str | None = None,
    command_runner: Callable[[Sequence[str], Path], None] | None = None,
) -> MonthlyCloseResult:
    """Execute the canonical source-adapter -> monthly-close path.

    Authentication must succeed before adapter ``fetch`` can run. The adapter's validated
    canonical tables are the only updates handed to the existing monthly-close authority.
    Successful acquisition provenance is retained separately from calculation/close state.
    """

    adapter_result = adapter.run(
        target_month,
        known_accounts=known_accounts,
        known_payment_methods=known_payment_methods,
        fetched_at=fetched_at,
    )
    write_provenance(
        repo_root / "data" / "state" / f"source-{adapter_result.provenance.source_id}.json",
        adapter_result.provenance,
    )
    port = FilesystemMonthlyClosePort(
        repo_root,
        target_month,
        updates=adapter_result_to_monthly_updates(adapter_result),
        command_runner=command_runner,
    )
    return MonthlyCloseWorkflow().execute(port)
