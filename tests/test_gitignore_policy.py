from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OPERATIONAL_PATTERNS = {
    "data/",
    "input.xlsx",
    "view.xlsx",
    "backup/",
    "~$*.xlsx",
    "*.tmp",
    "*conflicted copy*",
    "*Conflicted copy*",
    "/master/accounts.csv",
    "/master/payment_methods.csv",
}

PRIVATE_MASTER_PATHS = (
    ROOT / "master" / "accounts.csv",
    ROOT / "master" / "payment_methods.csv",
)
PUBLIC_MASTER_EXAMPLES = (
    ROOT / "master" / "accounts.example.csv",
    ROOT / "master" / "payment_methods.example.csv",
)


def _is_tracked(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def test_gitignore_blocks_sensitive_operational_files() -> None:
    gitignore = ROOT / ".gitignore"
    patterns = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert REQUIRED_OPERATIONAL_PATTERNS <= patterns


def test_private_financial_master_files_are_not_tracked() -> None:
    assert all(not _is_tracked(path) for path in PRIVATE_MASTER_PATHS)
    assert all(_is_tracked(path) for path in PUBLIC_MASTER_EXAMPLES)


def test_public_master_examples_do_not_name_real_financial_services() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_MASTER_EXAMPLES)
    forbidden = (
        "ゆうちょ",
        "ソニー銀行",
        "ドイツ銀行",
        "みんなの銀行",
        "城南信用金庫",
        "SBI証券",
        "楽天証券",
        "マネックス証券",
        "Binance",
        "三井住友カード",
        "楽天カード",
        "エポスカード",
        "メルカリカード",
    )
    assert all(name not in combined for name in forbidden)
