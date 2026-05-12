from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from opendream.util import sha256_path  # noqa: E402

VENDOR_DIR = REPO_ROOT / "opendream" / "static" / "vendor"
README = VENDOR_DIR / "README.md"


def documented_checksums(readme_text: str) -> dict[str, str]:
    pattern = re.compile(r"- `(?P<name>[^`]+)`: `(?P<sha>[0-9a-f]{64})`")
    return {match.group("name"): match.group("sha") for match in pattern.finditer(readme_text)}


def main() -> int:
    problems: list[str] = []
    if not README.is_file():
        print("vendor README missing", file=sys.stderr)
        return 1
    checksums = documented_checksums(README.read_text(encoding="utf-8"))
    js_files = sorted(path for path in VENDOR_DIR.glob("*.js") if path.name != "_test.js")
    if not js_files:
        problems.append("no vendored JavaScript files found")
    for path in js_files:
        actual = sha256_path(path)
        expected = checksums.get(path.name)
        if expected is None:
            problems.append(f"{path.name}: checksum missing from README")
        elif expected != actual:
            problems.append(f"{path.name}: checksum mismatch expected={expected} actual={actual}")
    notices = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
    if not notices.is_file():
        problems.append("THIRD_PARTY_NOTICES.md missing")
    else:
        notice_text = notices.read_text(encoding="utf-8")
        for expected in ("sigma.js", "graphology"):
            if expected not in notice_text:
                problems.append(f"THIRD_PARTY_NOTICES.md missing {expected} notice")
    if problems:
        print("vendor asset check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("vendor asset check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
