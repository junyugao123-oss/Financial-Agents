from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "services" / "api" / "app",
    ROOT / "scripts",
]
EXCLUDED = {Path(__file__).resolve()}

RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "negative-shift",
        re.compile(r"\.shift\s*\(\s*-\d+"),
        "Negative shift reads future rows and is forbidden in quant/data logic.",
    ),
    (
        "backward-fill",
        re.compile(r"\.bfill\s*\("),
        "Backward fill can move future low-frequency data into the past.",
    ),
    (
        "fillna-bfill",
        re.compile(r"\.fillna\s*\([^\n)]*(?:method\s*=\s*)?['\"]bfill['\"]"),
        "fillna(... bfill ...) can create look-ahead leakage.",
    ),
    (
        "date-merge",
        re.compile(r"\.merge\s*\([^\n)]*on\s*=\s*['\"]date['\"]"),
        "Plain date merge can leak daily factors into earlier intraday bars.",
    ),
]


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        if target.is_file() and target.suffix == ".py":
            files.append(target)
        elif target.is_dir():
            files.extend(path for path in target.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(path for path in files if path.resolve() not in EXCLUDED)


def main() -> int:
    findings: list[str] = []

    for path in iter_python_files():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for rule_id, pattern, message in RULES:
                if pattern.search(line):
                    rel = path.relative_to(ROOT)
                    findings.append(f"{rel}:{line_number}: {rule_id}: {message}")

    if findings:
        print("Quant safety audit failed:")
        for finding in findings:
            print(f"- {finding}")
        print("\nSee docs/ALGO_CARD.md and docs/DATA_SOURCES.md.")
        return 1

    print("Quant safety audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
