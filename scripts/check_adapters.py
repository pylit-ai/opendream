from __future__ import annotations

import json
import os
import re
import sys
from argparse import _SubParsersAction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

COMMAND_RE = re.compile(r"\bopendream\s+([a-z0-9-]+)")
REQUIRED_FILES = [
    ".meta/spec-adapters/claude-code/README.md",
    ".meta/spec-adapters/claude-code/hooks/example-settings.json",
    ".meta/spec-adapters/claude-code/skills/opendream-context/SKILL.md",
    ".meta/spec-adapters/claude-code/scripts/opendream-pre-task.sh",
    ".meta/spec-adapters/claude-code/scripts/opendream-post-task.sh",
    ".meta/spec-adapters/codex/README.md",
    ".meta/spec-adapters/codex/AGENTS.global.example.md",
    ".meta/spec-adapters/codex/AGENTS.project.snippet.md",
    ".meta/spec-adapters/codex/skills/opendream-context/SKILL.md",
    ".meta/spec-adapters/codex/scripts/opendream-pre-task.sh",
    ".meta/spec-adapters/codex/scripts/opendream-post-task.sh",
    ".meta/spec-adapters/openclaw/README.md",
    ".meta/spec-adapters/openclaw/event-map.md",
    ".meta/spec-adapters/openclaw/prompt-snippets/pre-plan.md",
    ".meta/spec-adapters/openclaw/prompt-snippets/post-task.md",
    ".meta/spec-adapters/openclaw/scripts/opendream-hooks.sh",
]


def cli_commands() -> set[str]:
    from opendream_memory.cli import build_parser

    parser = build_parser()
    for action in parser._actions:
        if isinstance(action, _SubParsersAction):
            return set(action.choices)
    raise RuntimeError("unable to discover CLI commands")


def main() -> int:
    commands = cli_commands()
    errors: list[str] = []

    for relative_path in REQUIRED_FILES:
        path = REPO_ROOT / relative_path
        if not path.exists():
            errors.append(f"missing file: {relative_path}")
            continue

        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid json: {relative_path}: {exc}")

        found_commands = COMMAND_RE.findall(text)
        for command in found_commands:
            if command not in commands:
                errors.append(f"unknown CLI command in {relative_path}: {command}")

        if "README.md" in path.name and "Canonical behavior lives in" not in text:
            errors.append(f"adapter README must point back to canonical sources: {relative_path}")

        if path.suffix == ".sh" and not os.access(path, os.X_OK):
            errors.append(f"shell script is not executable: {relative_path}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("adapter checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
