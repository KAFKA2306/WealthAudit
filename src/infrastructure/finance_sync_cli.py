from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.interface_adapters.command_driver import load_command_drivers
from src.use_cases.finance_acquisition import (
    archive_raw_artifact,
    coverage_rows,
    load_source_policies,
    load_source_state,
    mark_auth_required,
    mark_success,
    save_source_state,
)
from src.use_cases.finance_runner import run_acquisition_cycle


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _registry_path(args: argparse.Namespace) -> Path:
    return Path(args.registry or (_root() / "config" / "finance_sources.json"))


def _data_root(args: argparse.Namespace) -> Path:
    return Path(args.data_root or (_root() / "data"))


def _drivers_path(args: argparse.Namespace, data_root: Path) -> Path:
    return Path(args.drivers or (data_root / "runtime" / "driver_commands.json"))


def cmd_plan(args: argparse.Namespace) -> int:
    policies = load_source_policies(_registry_path(args))
    rows = coverage_rows(policies, state_dir=_data_root(args) / "state" / "sources")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    data_root = _data_root(args)
    policies = load_source_policies(_registry_path(args))
    drivers = load_command_drivers(
        _drivers_path(args, data_root),
        incoming_root=data_root / "incoming",
    )
    outcomes = run_acquisition_cycle(
        policies,
        drivers=drivers,
        data_root=data_root,
    )
    coverage = coverage_rows(policies, state_dir=data_root / "state" / "sources")
    payload = {"outcomes": outcomes, "coverage": coverage}
    report_path = data_root / "state" / "last-finance-sync.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    data_root = _data_root(args)
    state_path = data_root / "state" / "sources" / f"{args.source_id}.json"
    state = load_source_state(state_path, args.source_id)
    source_file = Path(args.path)
    artifact = archive_raw_artifact(
        root=data_root,
        source_id=args.source_id,
        account_alias=args.account_alias,
        raw=source_file.read_bytes(),
        original_filename=source_file.name,
        covered_from=args.covered_from,
        covered_to=args.covered_to,
    )
    updated = mark_success(state, artifact, record_count=args.record_count)
    save_source_state(state_path, updated)
    print(
        json.dumps(
            {"artifact": artifact.__dict__, "state": updated.__dict__},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_auth_required(args: argparse.Namespace) -> int:
    data_root = _data_root(args)
    state_path = data_root / "state" / "sources" / f"{args.source_id}.json"
    state = load_source_state(state_path, args.source_id)
    updated = mark_auth_required(state, error_code=args.error_code)
    save_source_state(state_path, updated)
    print(json.dumps(updated.__dict__, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retention-aware finance acquisition control plane"
    )
    parser.add_argument("--registry")
    parser.add_argument("--data-root")
    parser.add_argument(
        "--drivers",
        help="Local ignored driver config. Defaults to data/runtime/driver_commands.json",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Show source actions without touching providers")
    plan.set_defaults(func=cmd_plan)

    run = sub.add_parser(
        "run",
        help="Run all due local provider drivers; isolate auth/failure per source",
    )
    run.set_defaults(func=cmd_run)

    ingest = sub.add_parser(
        "ingest",
        help="Archive an official export and mark the source successful",
    )
    ingest.add_argument("source_id")
    ingest.add_argument("path")
    ingest.add_argument("--account-alias", default="default")
    ingest.add_argument("--covered-from")
    ingest.add_argument("--covered-to")
    ingest.add_argument("--record-count", type=int, default=0)
    ingest.set_defaults(func=cmd_ingest)

    auth = sub.add_parser(
        "auth-required",
        help="Stop only one provider at the human authentication boundary",
    )
    auth.add_argument("source_id")
    auth.add_argument("--error-code", default="AUTH_REQUIRED")
    auth.set_defaults(func=cmd_auth_required)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
