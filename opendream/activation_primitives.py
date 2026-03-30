from __future__ import annotations

import hashlib
import json
import re
import shlex
import stat
import subprocess
from pathlib import Path
from typing import Any

from .storage import MemoryStore
from .util import atomic_write_text

HOOKS_DIR = Path(".opendream/hooks")
BIN_DIR = Path(".opendream/bin")
CONTEXT_DIR = Path(".opendream/context")

CLAUDE_SETTINGS_PATH = Path(".claude/settings.json")
OPENCLAW_CONFIG_PATH = Path(".openclaw/config.json")
OPENCLAW_EVENT_MAP_PATH = Path(".openclaw/opendream-event-map.md")
CODEX_AGENTS_PATH = Path("AGENTS.md")

CURSOR_MDC_FRONTMATTER = """---
description: OpenDream workspace memory integration (managed by opendream activate)
globs: []
alwaysApply: true
---

"""

_MDC_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

LEGACY_CODEX_BLOCK_START = "<!-- OPENDREAM:CODEX START -->"
LEGACY_CODEX_BLOCK_END = "<!-- OPENDREAM:CODEX END -->"


def opendream_command(store: MemoryStore, command: str) -> str:
    flags = [
        "opendream",
        *command.split(),
        "--workspace",
        '"$WORKSPACE"',
        "--memory-dir",
        shlex.quote(store.memory_dir_name),
    ]
    if store.compat_mode != "canonical":
        flags.extend(["--compat-mode", shlex.quote(store.compat_mode)])
    return " ".join(flags)


def pre_task_script(store: MemoryStore, target: str) -> str:
    command = opendream_command(store, "prepare-context")
    output_name = f"{target}-pre-task.json"
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'QUERY="${1:-${OPENDREAM_QUERY:-current task}}"',
            'GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"',
            f'OUTPUT="$WORKSPACE/{CONTEXT_DIR}/{output_name}"',
            'mkdir -p "$(dirname "$OUTPUT")"',
            'if [ -n "$GLOBAL" ]; then',
            f'  {command} --query "$QUERY" --include-global --global-workspace "$GLOBAL" > "$OUTPUT"',
            "else",
            f'  {command} --query "$QUERY" > "$OUTPUT"',
            "fi",
            'cat "$OUTPUT"',
            "",
        ]
    )


def post_task_script(store: MemoryStore, target: str) -> str:
    emit_command = opendream_command(store, "emit-event")
    maintain_command = opendream_command(store, "maintain")
    worker_command = opendream_command(store, "dream worker")
    ref = f"{target}-post-task"
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"',
            f'MESSAGE_REF="${{OPENDREAM_REF:-{ref}}}"',
            f'{emit_command} --kind task_outcome --content "$SUMMARY" --message-ref "$MESSAGE_REF"',
            f"{maintain_command}",
            f"{worker_command} --once",
            "",
        ]
    )


def openclaw_hook_script(store: MemoryStore) -> str:
    prepare_command = opendream_command(store, "prepare-context")
    emit_command = opendream_command(store, "emit-event")
    maintain_command = opendream_command(store, "maintain")
    worker_command = opendream_command(store, "dream worker")
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'MODE="${1:-pre-plan}"',
            'PAYLOAD="${2:-${OPENCLAW_TASK:-current task}}"',
            'WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"',
            'GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"',
            f'OUTPUT="$WORKSPACE/{CONTEXT_DIR}/openclaw-pre-task.json"',
            'mkdir -p "$(dirname "$OUTPUT")"',
            'if [ "$MODE" = "pre-plan" ]; then',
            '  if [ -n "$GLOBAL" ]; then',
            f'    {prepare_command} --query "$PAYLOAD" --include-global --global-workspace "$GLOBAL" > "$OUTPUT"',
            "  else",
            f'    {prepare_command} --query "$PAYLOAD" > "$OUTPUT"',
            "  fi",
            '  cat "$OUTPUT"',
            "  exit 0",
            "fi",
            (
                f'{emit_command} --kind task_outcome --content "$PAYLOAD" '
                '--message-ref "${OPENCLAW_REF:-openclaw-post-task}"'
            ),
            f"{maintain_command}",
            f"{worker_command} --once",
            "",
        ]
    )


def codex_wrapper_script(store: MemoryStore) -> str:
    del store
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "",
            'SUMMARY="${OPENDREAM_SUMMARY:-Codex task completed.}"',
            'QUERY="${OPENDREAM_QUERY:-$SUMMARY}"',
            'if [ "${1:-}" = "--summary" ]; then',
            '  SUMMARY="$2"',
            "  shift 2",
            "fi",
            'if [ "${1:-}" = "--query" ]; then',
            '  QUERY="$2"',
            "  shift 2",
            "fi",
            'if [ "${1:-}" = "--" ]; then',
            "  shift",
            "fi",
            'sh .opendream/hooks/codex-pre-task.sh "$QUERY"',
            "status=0",
            'if [ "$#" -gt 0 ]; then',
            '  "$@" || status=$?',
            "fi",
            'post_status=0',
            'sh .opendream/hooks/codex-post-task.sh "$SUMMARY" || post_status=$?',
            'if [ "$status" -eq 0 ] && [ "$post_status" -ne 0 ]; then',
            '  status="$post_status"',
            "fi",
            'exit "$status"',
            "",
        ]
    )


def split_yaml_frontmatter(text: str) -> tuple[str, str]:
    stripped = text.lstrip("\ufeff")
    match = _MDC_FRONT_MATTER_RE.match(stripped)
    if not match:
        return CURSOR_MDC_FRONTMATTER, stripped
    return match.group(0), stripped[match.end() :].lstrip("\n")


def block_start(target: str) -> str:
    return f"<!-- BEGIN OPENDREAM MANAGED BLOCK: {target} -->"


def block_end(target: str) -> str:
    return f"<!-- END OPENDREAM MANAGED BLOCK: {target} -->"


def remove_block(text: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in text or end_marker not in text:
        return text
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return ((text[:start] + text[end:]).replace("\n\n\n", "\n\n")).lstrip("\n")


def replace_or_append_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    updated = remove_block(text, LEGACY_CODEX_BLOCK_START, LEGACY_CODEX_BLOCK_END)
    if start_marker in updated and end_marker in updated:
        start = updated.index(start_marker)
        end = updated.index(end_marker, start) + len(end_marker)
        if updated[end : end + 1] == "\n":
            end += 1
        tail = updated[end:]
        return updated[:start] + replacement + tail
    return updated.rstrip() + "\n\n" + replacement


def extract_block(text: str, start_marker: str, end_marker: str) -> str | None:
    if start_marker not in text or end_marker not in text:
        return None
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    tail = text[end:]
    if tail.startswith("\n"):
        end += 1
    return text[start:end]


def shell_hook_instruction_block(target_label: str, store: MemoryStore) -> str:
    del store
    pre_script = f"{target_label}-pre-task.sh"
    post_script = f"{target_label}-post-task.sh"
    return "\n".join(
        [
            block_start(target_label),
            "",
            "## OpenDream",
            "",
            "Before substantial work, run:",
            f'`sh .opendream/hooks/{pre_script} "${{OPENDREAM_QUERY:-current task}}"`',
            "",
            "Before the final response, run:",
            f'`sh .opendream/hooks/{post_script} "${{OPENDREAM_SUMMARY:-Task completed.}}"`',
            "",
            block_end(target_label),
            "",
        ]
    )


def codex_block(store: MemoryStore) -> str:
    del store
    return "\n".join(
        [
            block_start("codex"),
            "",
            "## OpenDream Activation",
            "",
            "Before substantial work, run:",
            '`sh .opendream/hooks/codex-pre-task.sh "${OPENDREAM_QUERY:-current task}"`',
            "",
            "Before the final response, run:",
            '`sh .opendream/hooks/codex-post-task.sh "${OPENDREAM_SUMMARY:-Task completed.}"`',
            "",
            "For scripted Codex entrypoints, prefer:",
            (
                '`sh .opendream/bin/codex-task-wrapper.sh '
                '--summary "${OPENDREAM_SUMMARY:-Task completed.}" -- <agent command>`'
            ),
            "",
            block_end("codex"),
            "",
        ]
    )


def openclaw_event_map() -> str:
    return "\n".join(
        [
            "# OpenDream OpenClaw event map",
            "",
            '- `planner.pre_plan` -> `sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"`',
            '- `worker.post_task` -> `sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"`',
            "",
        ]
    )


def merge_cursor_mdc(existing: str, store: MemoryStore, block_id: str) -> str:
    frontmatter, body = split_yaml_frontmatter(existing.strip() or "")
    block = shell_hook_instruction_block(block_id, store)
    new_body = replace_or_append_block(
        body if body.strip() else "",
        block_start(block_id),
        block_end(block_id),
        block,
    ).strip()
    return frontmatter.rstrip() + "\n" + new_body + "\n"


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def json_contains_expected(payload: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, value in expected.items():
        current = payload.get(key)
        if isinstance(value, dict):
            if not isinstance(current, dict) or not json_contains_expected(current, value):
                return False
        elif isinstance(value, list):
            if not isinstance(current, list):
                return False
            for item in value:
                if item not in current:
                    return False
        else:
            if current != value:
                return False
    return True


def write_if_changed(path: Path, content: str) -> list[str]:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return []
    atomic_write_text(path, content)
    return [str(path)]


def write_managed_script(path: Path, content: str) -> list[str]:
    changed = write_if_changed(path, content)
    if changed:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return changed


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_surface(target: str, relative_path: Path, kind: str, expected: str) -> dict[str, Any]:
    return {
        "target_kind": target,
        "path": str(relative_path),
        "kind": kind,
        "hash": sha256_text(expected),
        "mode": "file",
        "expected": expected,
    }


def json_surface(target: str, relative_path: Path, kind: str, expected: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_kind": target,
        "path": str(relative_path),
        "kind": kind,
        "hash": sha256_text(json.dumps(expected, sort_keys=True)),
        "mode": "json",
        "expected": expected,
    }


def block_surface(target: str, relative_path: Path, kind: str, expected: str, block_target: str) -> dict[str, Any]:
    return {
        "target_kind": target,
        "path": str(relative_path),
        "kind": kind,
        "hash": sha256_text(expected),
        "mode": "block",
        "expected": expected,
        "target": block_target,
    }


def assess_surface(workspace: Path, surface: dict[str, Any]) -> dict[str, Any]:
    path = workspace / surface["path"]
    state = "clean"
    detail = "surface is live"
    if surface["mode"] == "file":
        if not path.exists():
            state = "missing"
            detail = f"missing managed file {surface['path']}"
        else:
            content = path.read_text(encoding="utf-8")
            if content != surface["expected"]:
                state = "drifted"
                detail = f"managed file drift detected at {surface['path']}"
    elif surface["mode"] == "json":
        if not path.exists():
            state = "missing"
            detail = f"missing config file {surface['path']}"
        else:
            payload = load_json_object(path)
            if not json_contains_expected(payload, surface["expected"]):
                state = "drifted"
                detail = f"managed hook entries drifted at {surface['path']}"
    elif surface["mode"] == "block":
        if not path.exists():
            state = "missing"
            detail = f"missing block carrier {surface['path']}"
        else:
            text = path.read_text(encoding="utf-8")
            block = extract_block(text, block_start(surface["target"]), block_end(surface["target"]))
            if block != surface["expected"]:
                state = "drifted"
                detail = f"managed block drift detected at {surface['path']}"
    smoke = {"status": "passed", "detail": detail}
    if state == "clean" and surface["kind"] in {"hook-script", "managed-wrapper"}:
        check = subprocess.run(
            ["/bin/sh", "-n", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            state = "drifted"
            smoke = {"status": "failed", "detail": f"shell syntax check failed for {surface['path']}"}
    elif state != "clean":
        smoke = {"status": "failed", "detail": detail}
    return {
        "target_kind": surface["target_kind"],
        "path": surface["path"],
        "kind": surface["kind"],
        "hash": surface["hash"],
        "managed": True,
        "state": state,
        "smoke": smoke,
    }
