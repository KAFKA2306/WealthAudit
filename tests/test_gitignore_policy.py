from pathlib import Path


REQUIRED_OPERATIONAL_PATTERNS = {
    "data/",
    "input.xlsx",
    "view.xlsx",
    "backup/",
    "~$*.xlsx",
    "*.tmp",
    "*conflicted copy*",
    "*Conflicted copy*",
}


def test_gitignore_blocks_sensitive_operational_files() -> None:
    gitignore = Path(__file__).resolve().parents[1] / ".gitignore"
    patterns = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert REQUIRED_OPERATIONAL_PATTERNS <= patterns
