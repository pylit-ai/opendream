from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STALE_SUFFIXES = (".orig", ".bak")
STALE_NAMES = {".DS_Store"}


def main() -> int:
    problems: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if ".git" in path.parts or ".venv" in path.parts or ".tmp" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT)
        if path.name in STALE_NAMES or path.name.endswith(STALE_SUFFIXES):
            problems.append(str(rel))
    if problems:
        print("public artifact check failed:", file=sys.stderr)
        for problem in sorted(problems):
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("public artifact check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
