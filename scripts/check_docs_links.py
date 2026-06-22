from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _tracked_markdown_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO_ROOT)
    files = [entry.decode("utf-8") for entry in raw.split(b"\0") if entry]
    return [
        REPO_ROOT / path
        for path in files
        if path.lower().endswith((".md", ".mdx"))
    ]


def _normalize_target(raw: str) -> str | None:
    value = raw.strip()
    if (
        not value
        or value.startswith("#")
        or value.startswith("mailto:")
        or value.startswith("data:")
        or SCHEME_RE.match(value)
    ):
        return None
    target = value.split()[0].strip("<>")
    target = target.split("#", 1)[0].split("?", 1)[0]
    return unquote(target) if target else None


def _resolve_link(source: Path, target: str) -> Path:
    if target.startswith("/"):
        return (REPO_ROOT / target.lstrip("/")).resolve()
    return (source.parent / target).resolve()


def main() -> int:
    failures: list[str] = []
    checked = 0
    for file_path in _tracked_markdown_files():
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = _normalize_target(match.group(1))
            if target is None:
                continue
            checked += 1
            resolved = _resolve_link(file_path, target)
            try:
                relative_resolved = resolved.relative_to(REPO_ROOT)
            except ValueError:
                failures.append(f"{file_path.relative_to(REPO_ROOT)} -> {target} resolves outside repo")
                continue
            if not resolved.exists():
                failures.append(
                    f"{file_path.relative_to(REPO_ROOT)} -> {target} missing ({relative_resolved})",
                )

    if failures:
        print("docs link check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"docs link check passed ({checked} local links)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
