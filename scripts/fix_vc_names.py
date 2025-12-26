"""Script to fix duplicate sbi_sec,vc entries in assets.csv.
Multiple VC entries per month should be named vc_1, vc_2, vc_3 (sorted by value).
"""

import pandas as pd

df = pd.read_csv("data/input/assets.csv")

result_rows = []
processed_months = set()

for idx, row in df.iterrows():
    if row["account_id"] == "sbi_sec" and row["asset_class"] == "vc":
        month = row["month"]
        if month in processed_months:
            continue
        processed_months.add(month)

        month_vcs = df[
            (df["month"] == month)
            & (df["account_id"] == "sbi_sec")
            & (df["asset_class"] == "vc")
        ]

        if len(month_vcs) == 1:
            result_rows.append(row.to_dict())
        else:
            # Sort by balance, name vc_1 (smallest), vc_2, vc_3 (largest)
            sorted_vcs = month_vcs.sort_values("balance")
            for i, (_, vc_row) in enumerate(sorted_vcs.iterrows(), 1):
                new_row = vc_row.to_dict()
                new_row["asset_class"] = f"vc_{i}"
                result_rows.append(new_row)
    else:
        result_rows.append(row.to_dict())

new_df = pd.DataFrame(result_rows)
new_df.to_csv("data/input/assets.csv", index=False)
print(f"Fixed {len(new_df)} rows")
print("\nVC entries (last 20):")
print(new_df[new_df["asset_class"].str.startswith("vc")].tail(20))
