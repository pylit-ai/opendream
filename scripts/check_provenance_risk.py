from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("README.md", "docs", "opendream", "scripts", "tests", "CLEAN_ROOM.md", "THIRD_PARTY_NOTICES.md")
SKIP_PARTS = {".git", ".venv", ".tmp", "__pycache__", "dist", "build", "node_modules"}
TEXT_SUFFIXES = {".md", ".py", ".json", ".toml", ".yml", ".yaml", ".js", ".css", ".html", ".txt"}
ALLOWLIST = {
    "docs/benchmarks/autodream-comparison.md": "legacy comparison note retained as clean-room compatibility context",
}

RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private overlay marker", re.compile(r"opendream-private|archived-public-agent-artifacts")),
    ("local absolute path", re.compile(r"/Users/(?!example|me)[A-Za-z0-9_.-]+|/home/(?!example)[A-Za-z0-9_.-]+")),
    (
        "secret-looking assignment",
        re.compile(r"(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}", re.IGNORECASE),
    ),
    (
        "unsupported launch claim",
        re.compile(
            r"\b(state-of-the-art|guarantee[sd]?|best-in-class|first-of-its-kind|industry-first)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "generated private heading",
        re.compile(r"BEGIN .*PRIVATE|agent-artifact|customer/provider-specific", re.IGNORECASE),
    ),
    (
        "risky source URL",
        re.compile(
            r"https?://[^\s)]*(gist\.github|pastebin|system-prompts|claude-code-system-prompts)[^\s)]*",
            re.IGNORECASE,
        ),
    ),
)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        path = REPO_ROOT / root
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob("*"):
            if any(part in SKIP_PARTS for part in candidate.parts):
                continue
            if candidate.is_file() and candidate.suffix in TEXT_SUFFIXES:
                files.append(candidate)
    return sorted(files)


def allowed(rel: str, line: str, label: str) -> bool:
    if rel in ALLOWLIST and label in {"unsupported launch claim", "unattributed long URL"}:
        return True
    if rel == "CLEAN_ROOM.md" and "Claude Code" in line and "does not use leaked" in line:
        return True
    if rel == "docs/claims.md" and label == "unsupported launch claim":
        return True
    if rel == "KNOWN_LIMITATIONS.md" and label == "unsupported launch claim":
        return True
    if rel == "scripts/check_provenance_risk.py":
        return True
    if rel == "scripts/check_public_boundary.sh":
        return True
    if rel == "THIRD_PARTY_NOTICES.md" and label in {"unattributed long URL", "unsupported launch claim"}:
        return True
    return "github.com/pylit-ai/opendream" in line


def main() -> int:
    if not (REPO_ROOT / "CLEAN_ROOM.md").is_file():
        print("CLEAN_ROOM.md missing", file=sys.stderr)
        return 1
    problems: list[str] = []
    for path in iter_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for label, pattern in RISK_PATTERNS:
                if pattern.search(line) and not allowed(rel, line, label):
                    problems.append(f"{rel}:{line_no}: {label}: {line.strip()[:180]}")
    if problems:
        print("provenance risk check failed:", file=sys.stderr)
        for problem in problems[:200]:
            print(f"- {problem}", file=sys.stderr)
        if len(problems) > 200:
            print(f"- ... {len(problems) - 200} more", file=sys.stderr)
        return 1
    print("provenance risk check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
