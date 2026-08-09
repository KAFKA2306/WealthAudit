from __future__ import annotations

import hashlib
import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


class SourceAdapterError(ValueError):
    """Raised when an adapter cannot safely hand data to the monthly pipeline."""


@dataclass(frozen=True)
class SourceProvenance:
    source_id: str
    retrieved_at: str
    target_month: str
    record_count: int
    raw_sha256: str


@dataclass(frozen=True)
class AdapterResult:
    tables: Mapping[str, tuple[Mapping[str, Any], ...]]
    provenance: SourceProvenance


REQUIRED_FIELDS: Mapping[str, frozenset[str]] = {
    "income": frozenset({"month", "account_id", "amount"}),
    "expense": frozenset({"month", "method_id", "amount"}),
    "assets": frozenset({"month", "account_id", "asset_class", "balance"}),
    "market": frozenset({"month", "usd_jpy", "eur_jpy", "sp500"}),
}

IDENTITY_FIELDS: Mapping[str, tuple[str, ...]] = {
    "income": ("month", "account_id"),
    "expense": ("month", "method_id"),
    "assets": ("month", "account_id", "asset_class"),
    "market": ("month",),
}


class SourceAdapter(ABC):
    """Boundary for source-specific authentication and parsing.

    Implementations may understand provider-specific fields, but must return only the
    canonical income/expense/assets/market tables. Financial calculation is deliberately
    outside this contract.
    """

    source_id: str

    @abstractmethod
    def authenticate(self) -> Any:
        """Acquire ephemeral authorization context without transforming data."""

    @abstractmethod
    def fetch(self, auth_context: Any, target_month: str) -> bytes:
        """Fetch raw source bytes. Credentials must not be embedded in returned bytes."""

    @abstractmethod
    def parse(self, raw: bytes) -> Sequence[Mapping[str, Any]]:
        """Parse provider-specific records without financial calculation."""

    @abstractmethod
    def normalize(
        self, records: Sequence[Mapping[str, Any]], target_month: str
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        """Map source fields to canonical WealthAudit input tables."""

    def validate(
        self,
        tables: Mapping[str, Sequence[Mapping[str, Any]]],
        *,
        target_month: str,
        known_accounts: set[str],
        known_payment_methods: set[str],
    ) -> dict[str, tuple[Mapping[str, Any], ...]]:
        """Validate canonical output before handoff to the monthly workflow."""

        return validate_normalized_tables(
            tables,
            target_month=target_month,
            known_accounts=known_accounts,
            known_payment_methods=known_payment_methods,
        )

    def run(
        self,
        target_month: str,
        *,
        known_accounts: set[str],
        known_payment_methods: set[str],
        retrieved_at: str | None = None,
    ) -> AdapterResult:
        auth_context = self.authenticate()
        raw = self.fetch(auth_context, target_month)
        records = self.parse(raw)
        normalized = self.normalize(records, target_month)
        tables = self.validate(
            normalized,
            target_month=target_month,
            known_accounts=known_accounts,
            known_payment_methods=known_payment_methods,
        )
        provenance = SourceProvenance(
            source_id=self.source_id,
            retrieved_at=retrieved_at or datetime.now(timezone.utc).isoformat(),
            target_month=target_month,
            record_count=sum(len(rows) for rows in tables.values()),
            raw_sha256=hashlib.sha256(raw).hexdigest(),
        )
        return AdapterResult(tables=tables, provenance=provenance)


def validate_normalized_tables(
    tables: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    target_month: str,
    known_accounts: set[str],
    known_payment_methods: set[str],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    unknown_tables = set(tables) - set(REQUIRED_FIELDS)
    if unknown_tables:
        raise SourceAdapterError(f"unknown canonical tables: {sorted(unknown_tables)}")

    result: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for table, required in REQUIRED_FIELDS.items():
        rows = tuple(tables.get(table, ()))
        seen: set[tuple[Any, ...]] = set()
        for index, row in enumerate(rows):
            missing = required - set(row)
            if missing:
                raise SourceAdapterError(
                    f"{table}[{index}] missing fields: {sorted(missing)}"
                )
            if str(row["month"]) != target_month:
                raise SourceAdapterError(
                    f"{table}[{index}] month {row['month']!r} != {target_month!r}"
                )
            identity = tuple(row[field] for field in IDENTITY_FIELDS[table])
            if identity in seen:
                raise SourceAdapterError(
                    f"duplicate {table} identity: {identity!r}"
                )
            seen.add(identity)

            if table in {"income", "assets"}:
                account_id = str(row["account_id"])
                if account_id not in known_accounts:
                    raise SourceAdapterError(f"unknown account_id: {account_id}")
            if table == "expense":
                method_id = str(row["method_id"])
                if method_id not in known_payment_methods:
                    raise SourceAdapterError(f"unknown method_id: {method_id}")
        result[table] = rows
    return result


def write_provenance(path: Path, provenance: SourceProvenance) -> None:
    """Atomically persist non-secret audit metadata.

    Runtime callers should place this under the ignored ``data/`` tree. Raw payloads,
    cookies and tokens are intentionally not accepted by this function.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(provenance), ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
