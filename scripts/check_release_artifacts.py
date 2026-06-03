from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STALE_SUFFIXES = (".orig", ".bak")
STALE_NAMES = {".DS_Store"}
REQUIRED_PUBLIC_FILES = (
    "docs/provenance.md",
    "docs/known-limitations.md",
    "NOTICE",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "TRADEMARKS.md",
    "docs/claims.md",
    "docs/launch-readiness.md",
    "docs/release-protocol.md",
    "docs/technical-notes/dreaming-memory-change-control.md",
    "opendream/schema/release-evidence.schema.json",
)


def main() -> int:
    problems: list[str] = []
    for required in REQUIRED_PUBLIC_FILES:
        if not (REPO_ROOT / required).is_file():
            problems.append(required)
    for path in REPO_ROOT.rglob("*"):
        if ".git" in path.parts or ".venv" in path.parts or ".tmp" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT)
        if path.name in STALE_NAMES or path.name.endswith(STALE_SUFFIXES):
            problems.append(str(rel))
    if problems:
        print("release artifact check failed:", file=sys.stderr)
        for problem in sorted(problems):
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("release artifact check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
