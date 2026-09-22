from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.use_cases.finance_acquisition import (
    SourcePolicy,
    SourceState,
    acquisition_decision,
    archive_raw_artifact,
    load_source_policies,
    load_source_state,
    mark_auth_required,
    mark_success,
    save_source_state,
)


def _policy(**overrides):
    payload = {
        "source_id": "card",
        "priority": "P0",
        "acquisition_method": "official_csv",
        "cadence_days": 30,
        "retention_days": 60,
        "safety_margin_days": 10,
        "official_reference": "https://example.invalid/docs",
    }
    payload.update(overrides)
    return SourcePolicy(**payload)


def test_new_source_is_due_immediately():
    now = datetime(2026, 9, 22, tzinfo=timezone.utc)
    decision = acquisition_decision(_policy(), None, now=now)
    assert decision.action == "ACQUIRE"
    assert decision.reason == "never_successfully_acquired"


def test_fresh_source_is_not_reacquired_before_effective_interval():
    now = datetime(2026, 9, 22, tzinfo=timezone.utc)
    state = SourceState(
        source_id="card",
        status="OK",
        last_success_at="2026-09-10T00:00:00+00:00",
    )
    decision = acquisition_decision(_policy(), state, now=now)
    assert decision.action == "NOOP"


def test_retention_guard_caps_slow_cadence():
    policy = _policy(cadence_days=90, retention_days=60, safety_margin_days=10)
    assert policy.effective_interval_days() == 50
    state = SourceState(
        source_id="card",
        status="OK",
        last_success_at="2026-07-01T00:00:00+00:00",
    )
    decision = acquisition_decision(
        policy,
        state,
        now=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
    assert decision.action == "ACQUIRE"


def test_auth_required_is_isolated_from_acquisition_loop():
    state = SourceState(
        source_id="card",
        status="OK",
        last_success_at="2026-09-20T00:00:00+00:00",
    )
    blocked = mark_auth_required(state, attempted_at="2026-09-22T00:00:00+00:00")
    decision = acquisition_decision(
        _policy(),
        blocked,
        now=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
    assert decision.action == "WAIT_FOR_AUTH"
    assert blocked.last_success_at == state.last_success_at


def test_raw_archive_is_content_addressed_and_idempotent(tmp_path: Path):
    first = archive_raw_artifact(
        root=tmp_path,
        source_id="card",
        account_alias="primary",
        raw=b"date,amount\n2026-09-01,100\n",
        original_filename="statement.csv",
        acquired_at="2026-09-22T00:00:00+00:00",
        covered_from="2026-09-01",
        covered_to="2026-09-21",
    )
    second = archive_raw_artifact(
        root=tmp_path,
        source_id="card",
        account_alias="primary",
        raw=b"date,amount\n2026-09-01,100\n",
        original_filename="statement.csv",
        acquired_at="2026-09-22T00:00:00+00:00",
        covered_from="2026-09-01",
        covered_to="2026-09-21",
    )
    assert first.raw_sha256 == second.raw_sha256
    assert first.created is True
    assert second.created is False
    assert (tmp_path / first.path).exists()


def test_success_state_counts_only_new_raw_files(tmp_path: Path):
    state = SourceState(source_id="card")
    artifact = archive_raw_artifact(
        root=tmp_path,
        source_id="card",
        account_alias="primary",
        raw=b"x",
        original_filename="x.csv",
        acquired_at="2026-09-22T00:00:00+00:00",
    )
    updated = mark_success(state, artifact, record_count=3)
    duplicate = archive_raw_artifact(
        root=tmp_path,
        source_id="card",
        account_alias="primary",
        raw=b"x",
        original_filename="x.csv",
        acquired_at="2026-09-22T00:00:00+00:00",
    )
    updated2 = mark_success(updated, duplicate, record_count=3)
    assert updated.raw_file_count == 1
    assert updated2.raw_file_count == 1


def test_state_round_trip(tmp_path: Path):
    path = tmp_path / "state" / "card.json"
    state = SourceState(
        source_id="card",
        status="OK",
        last_success_at="2026-09-22T00:00:00+00:00",
        record_count=10,
    )
    save_source_state(path, state)
    assert load_source_state(path, "card") == state


def test_repository_registry_is_machine_readable():
    root = Path(__file__).resolve().parents[1]
    policies = load_source_policies(root / "config" / "finance_sources.json")
    ids = {policy.source_id for policy in policies}
    assert {"mobile_suica", "jonan_shinkin", "rakuten_card", "vpass", "paypay"} <= ids
    payload = json.loads((root / "config" / "finance_sources.json").read_text())
    assert payload["schema_version"] == "wealthaudit.finance-sources.v1"
