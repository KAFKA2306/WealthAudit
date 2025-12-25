import csv
from pathlib import Path


def to_enum(val: str) -> str:
    return val.upper().replace("-", "_").replace(" ", "_")


def main():
    root = Path(__file__).parent.parent
    master = root / "master"
    dest = root / "src" / "constants.py"

    code = ["from enum import Enum", "", ""]

    code.append("class AccountId(str, Enum):")
    with open(master / "accounts.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            code.append(f"    {to_enum(r['account_id'])} = '{r['account_id']}'")
    code.append("")
    code.append("")

    code.append("class AssetClassId(str, Enum):")
    with open(master / "asset_classes.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            code.append(f"    {to_enum(r['class_id'])} = '{r['class_id']}'")
    code.append("")
    code.append("")

    code.append("class PaymentMethodId(str, Enum):")
    with open(master / "payment_methods.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            code.append(f"    {to_enum(r['method_id'])} = '{r['method_id']}'")
    code.append("")

    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(code) + "\n")

    print(f"Generated {dest}")


if __name__ == "__main__":
    main()
