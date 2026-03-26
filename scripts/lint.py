from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def iter_text_files() -> list[Path]:
    patterns = [
        "opendream_memory/*.py",
        "tests/*.py",
        "tests/fixtures/*.jsonl",
        "specs/**/*.md",
        "openspec/**/*.md",
        "openspec/**/*.json",
        "openspec/**/*.yaml",
        "docs/**/*.md",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(REPO_ROOT.glob(pattern))
    return sorted({path for path in files if path.is_file()})


def check_whitespace(path: Path) -> list[str]:
    issues: list[str] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.rstrip() != line:
            issues.append(f"{path.relative_to(REPO_ROOT)}:{index}: trailing whitespace")
        if "\t" in line:
            issues.append(f"{path.relative_to(REPO_ROOT)}:{index}: tab character")
    return issues


def check_jsonl(path: Path) -> list[str]:
    issues: list[str] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"{path.relative_to(REPO_ROOT)}:{index}: invalid JSONL ({exc})")
    return issues


def main() -> int:
    issues: list[str] = []
    for path in iter_text_files():
        issues.extend(check_whitespace(path))
        if path.suffix == ".jsonl":
            issues.extend(check_jsonl(path))

    if issues:
        print("\n".join(issues))
        return 1

    print("lint ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
