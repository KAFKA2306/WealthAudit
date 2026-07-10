import pandas as pd

from scripts.forecast import forecast_income_by_stream


def test_main_salary_stream_migrates_from_sony_history_to_rakuten_forecast() -> None:
    accounts = pd.DataFrame(
        [
            {"account_id": "sony", "name": "ソニー銀行", "type": "bank", "risk": 0},
            {"account_id": "rakuten", "name": "楽天銀行", "type": "bank", "risk": 0},
        ]
    )
    streams = pd.DataFrame(
        [
            {
                "stream_id": "main_salary",
                "display_name": "主給与",
                "kind": "cash_income",
                "source_account_ids": "sony;rakuten",
                "forecast_to_account_id": "rakuten",
            }
        ]
    )
    history = pd.DataFrame(
        {
            "month": [
                "2026-01",
                "2026-02",
                "2026-03",
                "2026-04",
                "2026-05",
                "2026-06",
            ],
            "収入_ソニー銀行": [300000, 300000, 0, 0, 0, 0],
            "収入_楽天銀行": [0, 0, 320000, 320000, 320000, 320000],
        }
    )

    forecast_income, stream_amounts = forecast_income_by_stream(
        history,
        ["収入_ソニー銀行", "収入_楽天銀行"],
        ["2026-07"],
        accounts,
        streams,
    )

    assert forecast_income.loc["2026-07", "収入_楽天銀行"] == 320000
    assert forecast_income.loc["2026-07", "収入_ソニー銀行"] == 0
    assert stream_amounts.loc["2026-07", "main_salary"] == 320000


def test_other_cash_income_streams_forecast_by_master_metadata() -> None:
    accounts = pd.DataFrame(
        [
            {"account_id": "yucho", "name": "ゆうちょ銀行", "type": "bank", "risk": 0},
            {"account_id": "deutsche", "name": "ドイツ銀行", "type": "bank", "risk": 0},
            {"account_id": "jonan", "name": "城南信用金庫", "type": "bank", "risk": 0},
        ]
    )
    streams = pd.DataFrame(
        [
            {
                "stream_id": "yucho_cash_income",
                "display_name": "cash stream",
                "kind": "cash_income",
                "source_account_ids": "yucho",
                "forecast_to_account_id": "yucho",
            },
            {
                "stream_id": "deutsche_cash_income",
                "display_name": "cash stream",
                "kind": "cash_income",
                "source_account_ids": "deutsche",
                "forecast_to_account_id": "deutsche",
            },
            {
                "stream_id": "jonan_cash_income",
                "display_name": "cash stream",
                "kind": "cash_income",
                "source_account_ids": "jonan",
                "forecast_to_account_id": "jonan",
            },
        ]
    )
    history = pd.DataFrame(
        {
            "month": [
                "2026-01",
                "2026-02",
                "2026-03",
                "2026-04",
                "2026-05",
                "2026-06",
            ],
            "収入_ゆうちょ銀行": [10000, 10000, 10000, 10000, 10000, 10000],
            "収入_ドイツ銀行": [20000, 20000, 20000, 20000, 20000, 20000],
            "収入_城南信用金庫": [30000, 30000, 30000, 30000, 30000, 30000],
        }
    )

    forecast_income, stream_amounts = forecast_income_by_stream(
        history,
        ["収入_ゆうちょ銀行", "収入_ドイツ銀行", "収入_城南信用金庫"],
        ["2026-07"],
        accounts,
        streams,
    )

    assert forecast_income.loc["2026-07", "収入_ゆうちょ銀行"] == 10000
    assert forecast_income.loc["2026-07", "収入_ドイツ銀行"] == 20000
    assert forecast_income.loc["2026-07", "収入_城南信用金庫"] == 30000
    assert stream_amounts.loc["2026-07", "yucho_cash_income"] == 10000
    assert stream_amounts.loc["2026-07", "deutsche_cash_income"] == 20000
    assert stream_amounts.loc["2026-07", "jonan_cash_income"] == 30000
