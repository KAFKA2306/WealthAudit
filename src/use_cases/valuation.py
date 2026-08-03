from __future__ import annotations

from bisect import bisect_right
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from src.constants import AccountId, Currency
from src.domain.entities.models import Account, Asset, AssetValuation, Market, Month


def previous_month(month: str) -> str:
    value = datetime.strptime(month, "%Y-%m")
    year = value.year if value.month > 1 else value.year - 1
    month_number = value.month - 1 if value.month > 1 else 12
    return f"{year:04d}-{month_number:02d}"


def is_consecutive_month(previous: str, current: str) -> bool:
    return previous_month(current) == previous


def latest_market_at_or_before(
    month: str, markets: Sequence[Market]
) -> Market | None:
    """Return the latest observed market row, never a future row."""
    if not markets:
        return None
    ordered = sorted(markets, key=lambda item: str(item.month))
    months = [str(item.month) for item in ordered]
    index = bisect_right(months, month) - 1
    return ordered[index] if index >= 0 else None


def effective_currency(asset: Asset, account: Account) -> Currency:
    if asset.native_currency is not None:
        if asset.native_currency == Currency.MULTI:
            raise ValueError("Asset row currency cannot be 'multi'")
        return asset.native_currency
    if account.currency == Currency.MULTI:
        raise ValueError(
            "A multi-currency account requires native_currency on every asset row: "
            f"{asset.account_id.value}/{asset.asset_class.value}/{asset.month}"
        )
    return account.currency


def conversion_rate(currency: Currency, market: Market | None, month: str) -> float:
    if currency == Currency.JPY:
        return 1.0
    if market is None:
        raise ValueError(
            f"Market data is required to convert {currency.value} asset at or before {month}"
        )
    if currency == Currency.USD:
        return market.usd_jpy
    if currency == Currency.EUR:
        return market.eur_jpy
    raise ValueError(f"Unsupported valuation currency: {currency.value}")


def value_asset(
    asset: Asset,
    account: Account,
    markets: Sequence[Market],
) -> AssetValuation:
    currency = effective_currency(asset, account)
    market = latest_market_at_or_before(str(asset.month), markets)
    rate = conversion_rate(currency, market, str(asset.month))
    return AssetValuation(
        month=Month(str(asset.month)),
        account_id=asset.account_id,
        asset_class=asset.asset_class,
        native_currency=currency,
        native_balance=asset.native_balance,
        fx_rate_to_jpy=rate,
        jpy_value=asset.native_balance * rate,
    )


def value_assets(
    assets: Iterable[Asset],
    markets: Sequence[Market],
    accounts: Iterable[Account],
) -> list[AssetValuation]:
    account_map: Mapping[AccountId, Account] = {
        account.id: account for account in accounts
    }
    valuations: list[AssetValuation] = []
    for asset in assets:
        account = account_map.get(asset.account_id)
        if account is None:
            raise ValueError(f"Unknown account_id: {asset.account_id.value}")
        valuations.append(value_asset(asset, account, markets))
    return valuations
