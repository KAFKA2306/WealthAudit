from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from src.interface_adapters.zaim_api import (
    ZaimApiClient,
    ZaimApiError,
    ZaimOAuthCredentials,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _credentials() -> ZaimOAuthCredentials | None:
    names = (
        "ZAIM_CONSUMER_KEY",
        "ZAIM_CONSUMER_SECRET",
        "ZAIM_ACCESS_TOKEN",
        "ZAIM_ACCESS_TOKEN_SECRET",
    )
    values = [os.environ.get(name) for name in names]
    if not all(values):
        return None
    return ZaimOAuthCredentials(*[str(value) for value in values])


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    credentials = _credentials()
    if credentials is None:
        _print(
            {
                "status": "AUTH_REQUIRED",
                "error_code": "ZAIM_OAUTH_CREDENTIALS_REQUIRED",
            }
        )
        return 20

    start_date = os.environ.get("ZAIM_START_DATE")
    end_date = os.environ.get("ZAIM_END_DATE")
    client = ZaimApiClient(credentials)

    try:
        pages, records = client.fetch_money_pages(
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPError as exc:
        if exc.code in {401, 403}:
            _print({"status": "AUTH_REQUIRED", "error_code": f"ZAIM_HTTP_{exc.code}"})
            return 20
        _print({"status": "FAILED", "error_code": f"ZAIM_HTTP_{exc.code}"})
        return 1
    except (URLError, TimeoutError):
        _print({"status": "FAILED", "error_code": "ZAIM_NETWORK_ERROR"})
        return 1
    except ZaimApiError:
        _print({"status": "FAILED", "error_code": "ZAIM_SCHEMA_CHANGED"})
        return 1

    dates = sorted(
        str(item["date"])
        for item in records
        if item.get("date") is not None and len(str(item["date"])) >= 10
    )
    covered_from = dates[0][:10] if dates else start_date
    covered_to = dates[-1][:10] if dates else end_date

    data_root = Path(os.environ.get("WEALTHAUDIT_DATA_ROOT", _root() / "data"))
    incoming = data_root / "incoming" / "zaim"
    incoming.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = incoming / f"zaim-money-{stamp}.zip"

    manifest = {
        "schema_version": "wealthaudit.zaim-pages.v1",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "record_count": len(records),
        "page_count": len(pages),
        "pages": [
            {
                "name": f"page-{index:04d}.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_size": len(raw),
            }
            for index, raw in enumerate(pages, start=1)
        ],
    }

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        for index, raw in enumerate(pages, start=1):
            archive.writestr(f"page-{index:04d}.json", raw)

    _print(
        {
            "status": "SUCCESS",
            "path": str(target.resolve()),
            "original_filename": target.name,
            "account_alias": "zaim",
            "covered_from": covered_from,
            "covered_to": covered_to or date.today().isoformat(),
            "record_count": len(records),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
