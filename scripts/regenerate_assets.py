"""Regenerate assets.csv from legacy.csv with correct column mappings."""

import pandas as pd
import re

# Based on legacy.csv header analysis:
# Row 3-6 define columns. Asset data starts around column 23.
# Columns 33-35 near VC area:
#   33: 米株式 (stock_us)
#   34: VC
#   35: Binance
#   36: 楽天証券 (fund values)
#   37: Monex証券 (stock_us values)
# The 3 "VC" values in old assets.csv (142k, 201k, 3.8M) are actually:
#   - rakuten_sec (142k)
#   - monex_sec (201k)
#   - sbi_sec,vc (3.8M)

COLUMN_MAP = {
    23: ("jonan", "cash"),  # 城南信用金庫
    24: ("yucho", "cash"),  # ゆうちょ銀行
    25: ("sony", "cash"),  # Sony
    26: ("wise", "cash"),  # WISE
    27: ("deutsche", "cash"),  # ドイツ銀行
    28: ("minna", "cash"),  # みんなの銀行
    29: ("sbi_sec", "cash"),  # SBI銀行
    30: ("sbi_sec", "fx"),  # FX
    31: ("sbi_sec", "fund"),  # 投信
    32: ("sbi_sec", "stock_jp"),  # 日本株
    33: ("sbi_sec", "stock_us"),  # 米株式
    34: ("sbi_sec", "vc"),  # VC (the large value ~3.8M)
    35: ("binance", "crypto"),  # Binance
    36: ("rakuten_sec", "fund"),  # 楽天証券 (the ~142k value)
    37: ("monex_sec", "stock_us"),  # Monex証券 (the ~201k value)
    38: ("kosei_nenkin", "pension"),  # 厚生年金
    39: ("dc", "pension"),  # 確定拠出年金
}


def parse_value(val):
    """Parse a value like ¥1,234,567 or 1234567 to int."""
    if pd.isna(val) or val == "" or val == "¥0":
        return None
    val = str(val).replace("¥", "").replace(",", "").replace('"', "").strip()
    if val == "" or val == "0":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# Read the CSV skipping the header rows
df = pd.read_csv("data/input/legacy.csv", skiprows=7, header=None, encoding="utf-8")

assets_data = []

for idx, row in df.iterrows():
    # First column is the month (format: 2020/09/)
    month_raw = str(row[0]).strip()
    if not month_raw or not re.match(r"\d{4}/\d{2}/", month_raw):
        continue

    # Convert 2020/09/ to 2020-09
    month = month_raw.replace("/", "-")[:7]

    for col_idx, (account_id, asset_class) in COLUMN_MAP.items():
        if col_idx >= len(row):
            continue

        balance = parse_value(row[col_idx])
        if balance is not None and balance > 0:
            assets_data.append(
                {
                    "month": month,
                    "account_id": account_id,
                    "asset_class": asset_class,
                    "balance": balance,
                }
            )

# Create DataFrame and save
result_df = pd.DataFrame(assets_data)
result_df = result_df.sort_values(["month", "account_id", "asset_class"])
result_df.to_csv("data/input/assets.csv", index=False)

print(f"Generated {len(result_df)} rows")
print("\nSample of last 20 rows:")
print(result_df.tail(20))
print("\nUnique account_id + asset_class combinations:")
print(result_df.groupby(["account_id", "asset_class"]).size())
