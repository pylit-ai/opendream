from __future__ import annotations

import py_compile
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def iter_python_files() -> list[Path]:
    roots = [REPO_ROOT / "opendream_memory", REPO_ROOT / "tests", REPO_ROOT / "scripts"]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(root.rglob("*.py"))
    return sorted(files)


def main() -> int:
    for path in iter_python_files():
        py_compile.compile(str(path), doraise=True)
    print("typecheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
