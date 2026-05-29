"""Transcript ingestion: bridge external session JSONL formats into the
``store.transcripts_dir`` shape that the dream pipeline reads.

Claude Code session JSONL files (under ``~/.claude/projects/<slug>/``) carry
nested message structures that ``opendream/episodes.py`` cannot parse directly.
This module flattens them to ``{timestamp, speaker, text, session_id,
source_path}`` so the existing episode loader works without modification.

Exported surface:
    flatten_claude_row(row)            -> dict | None
    flatten_codex_row(row)             -> dict | None
    ingest_claude_sessions(store, src) -> dict (summary)
    ingest_codex_sessions(store, src)  -> dict (summary)
    auto_detect_claude_project_dir(workspace) -> Path | None
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .storage import MemoryStore

CLAUDE_PROJECTS_ROOT = Path.home() / ".claude" / "projects"
CODEX_SESSIONS_ROOT = Path.home() / ".codex" / "sessions"


def auto_detect_claude_project_dir(workspace: str | Path) -> Path | None:
    """Map an absolute workspace path to its Claude Code project session dir.

    Claude Code encodes the workspace path with `/` -> `-`, prefixed with `-`,
    e.g. ``/Users/me/src/foo`` becomes ``-Users-me-src-foo``.
    """
    abs_path = str(Path(workspace).expanduser().resolve())
    slug = "-" + abs_path.lstrip("/").replace("/", "-")
    candidate = CLAUDE_PROJECTS_ROOT / slug
    return candidate if candidate.is_dir() else None


def auto_detect_codex_sessions_dir() -> Path | None:
    """Return the well-known Codex session root when present."""
    return CODEX_SESSIONS_ROOT if CODEX_SESSIONS_ROOT.is_dir() else None


def _extract_text(message: Any) -> str:
    """Pull the human-readable text out of a Claude message blob."""
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, dict):
                if chunk.get("type") == "text" and isinstance(chunk.get("text"), str):
                    parts.append(chunk["text"])
                elif chunk.get("type") == "tool_use":
                    name = chunk.get("name", "")
                    parts.append(f"[tool_use:{name}]")
                elif chunk.get("type") == "tool_result":
                    parts.append("[tool_result]")
            elif isinstance(chunk, str):
                parts.append(chunk)
        return "\n".join(p for p in parts if p).strip()
    return ""


def _extract_codex_text(row: dict[str, Any]) -> str:
    for key in ("text", "content", "message", "input", "output"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    item = row.get("item")
    if isinstance(item, dict):
        text = _extract_codex_text(item)
        if text:
            return text
    content = row.get("content")
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                chunk_text = chunk.get("text") or chunk.get("content")
                if isinstance(chunk_text, str):
                    parts.append(chunk_text)
        return "\n".join(part for part in parts if part).strip()
    return ""


def _normalize_codex_row(row: dict[str, Any]) -> dict[str, Any]:
    """Unwrap current Codex JSONL envelopes into message-like rows."""
    payload = row.get("payload")
    if row.get("type") == "response_item" and isinstance(payload, dict):
        normalized = dict(payload)
        if "timestamp" not in normalized and isinstance(row.get("timestamp"), str):
            normalized["timestamp"] = row["timestamp"]
        if "id" not in normalized and isinstance(row.get("id"), str):
            normalized["id"] = row["id"]
        return normalized
    return row


def _codex_row_workspace(row: dict[str, Any]) -> str | None:
    payload = row.get("payload")
    candidates = [payload, row] if isinstance(payload, dict) else [row]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        value = (
            candidate.get("cwd")
            or candidate.get("current_working_directory")
            or candidate.get("workspace")
        )
        if isinstance(value, str) and value:
            return str(Path(value).expanduser().resolve())
    return None


def flatten_claude_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a Claude session JSONL row to the episode-loader shape.

    Returns None for rows that are not user/assistant turns (attachments,
    system events, snapshots, etc.).
    """
    row_type = row.get("type")
    if row_type not in ("user", "assistant"):
        return None
    timestamp = row.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        return None
    text = _extract_text(row.get("message"))
    if not text:
        return None
    return {
        "timestamp": timestamp,
        "speaker": row_type,
        "text": text,
        "session_id": row.get("sessionId") or row.get("session_id"),
        "id": row.get("uuid") or row.get("id"),
    }


def flatten_codex_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Convert common Codex session JSONL rows to episode-loader shape."""
    row = _normalize_codex_row(row)
    role = str(row.get("role") or row.get("type") or "").lower()
    item = row.get("item")
    if isinstance(item, dict) and not role:
        role = str(item.get("role") or item.get("type") or "").lower()
    if role not in {"user", "assistant"}:
        return None
    timestamp = row.get("timestamp") or row.get("created_at")
    if isinstance(item, dict):
        timestamp = timestamp or item.get("timestamp") or item.get("created_at")
    if not isinstance(timestamp, str) or not timestamp:
        return None
    text = _extract_codex_text(row)
    if not text:
        return None
    return {
        "timestamp": timestamp,
        "speaker": role,
        "text": text,
        "session_id": row.get("session_id") or row.get("id"),
        "id": row.get("uuid") or row.get("id"),
    }


def ingest_claude_sessions(
    store: MemoryStore,
    source_dir: Path | str,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Walk every ``*.jsonl`` under ``source_dir`` and write flattened
    episode rows into ``store.transcripts_dir``.

    Returns a summary suitable for CLI / API consumption.
    """
    src = Path(source_dir).expanduser()
    if not src.is_dir():
        return {"status": "missing-source", "source_dir": str(src), "ingested": 0}

    store.ensure_layout()
    target_dir = store.transcripts_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    files_seen = 0
    files_written = 0
    files_skipped = 0
    rows_in = 0
    rows_out = 0
    written_paths: list[str] = []

    for jsonl_path in sorted(src.glob("*.jsonl")):
        files_seen += 1
        target = target_dir / jsonl_path.name
        if target.exists() and not overwrite and target.stat().st_size > 0:
            files_skipped += 1
            continue
        flattened: list[dict[str, Any]] = []
        try:
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rows_in += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out = flatten_claude_row(row)
                if out is not None:
                    flattened.append(out)
        except OSError:
            continue
        if not flattened:
            files_skipped += 1
            continue
        # Atomic write: tempfile + rename.
        tmp = target.with_suffix(target.suffix + ".tmp")
        body = "\n".join(json.dumps(row, ensure_ascii=False) for row in flattened) + "\n"
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, target)
        files_written += 1
        rows_out += len(flattened)
        written_paths.append(str(target))

    return {
        "status": "ingested" if files_written else "no-op",
        "source_dir": str(src),
        "target_dir": str(target_dir),
        "files_seen": files_seen,
        "files_written": files_written,
        "files_skipped": files_skipped,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "written_paths_sample": written_paths[:5],
    }


def ingest_codex_sessions(
    store: MemoryStore,
    source_dir: Path | str,
    *,
    overwrite: bool = False,
    workspace_filter: Path | str | None = None,
) -> dict[str, Any]:
    """Walk Codex session JSONL files and write flattened transcript rows."""
    src = Path(source_dir).expanduser()
    if not src.is_dir():
        return {"status": "missing-source", "source_dir": str(src), "ingested": 0}

    store.ensure_layout()
    target_dir = store.transcripts_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    files_seen = 0
    files_written = 0
    files_skipped = 0
    rows_in = 0
    rows_out = 0
    written_paths: list[str] = []
    files_filtered = 0
    workspace_filter_path = (
        str(Path(workspace_filter).expanduser().resolve())
        if workspace_filter is not None
        else None
    )

    for jsonl_path in sorted(src.rglob("*.jsonl")):
        files_seen += 1
        relative_name = "_".join(jsonl_path.relative_to(src).parts)
        target = target_dir / relative_name
        if target.exists() and not overwrite and target.stat().st_size > 0:
            files_skipped += 1
            continue
        flattened: list[dict[str, Any]] = []
        file_matches_workspace = workspace_filter_path is None
        try:
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rows_in += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    workspace_filter_path is not None
                    and _codex_row_workspace(row) == workspace_filter_path
                ):
                    file_matches_workspace = True
                out = flatten_codex_row(row)
                if out is not None:
                    flattened.append(out)
        except OSError:
            continue
        if not file_matches_workspace:
            files_filtered += 1
            continue
        if not flattened:
            files_skipped += 1
            continue
        tmp = target.with_suffix(target.suffix + ".tmp")
        body = "\n".join(json.dumps(row, ensure_ascii=False) for row in flattened) + "\n"
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, target)
        files_written += 1
        rows_out += len(flattened)
        written_paths.append(str(target))

    return {
        "status": "ingested" if files_written else "no-op",
        "source_dir": str(src),
        "target_dir": str(target_dir),
        "files_seen": files_seen,
        "files_written": files_written,
        "files_skipped": files_skipped,
        "files_filtered": files_filtered,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "workspace_filter": workspace_filter_path,
        "written_paths_sample": written_paths[:5],
    }


def ingest_claude_for_workspace(
    store: MemoryStore,
    *,
    overwrite: bool = False,
    explicit_source: Path | str | None = None,
) -> dict[str, Any]:
    """Convenience: auto-detect Claude project dir for the workspace, then ingest."""
    if explicit_source is not None:
        source = Path(explicit_source).expanduser()
    else:
        detected = auto_detect_claude_project_dir(store.workspace)
        if detected is None:
            codex_detected = auto_detect_codex_sessions_dir()
            if codex_detected is not None:
                return ingest_codex_sessions(
                    store,
                    codex_detected,
                    overwrite=overwrite,
                    workspace_filter=store.workspace,
                )
            return {
                "status": "no-agent-transcripts",
                "workspace": str(store.workspace),
                "expected_dirs": [
                    str(
                        CLAUDE_PROJECTS_ROOT
                        / ("-" + str(Path(store.workspace).resolve()).lstrip("/").replace("/", "-"))
                    ),
                    str(CODEX_SESSIONS_ROOT),
                ],
                "hint": "Pass --from /path/to/session/jsonl-dir explicitly if sessions live elsewhere.",
            }
        source = detected
    return ingest_claude_sessions(store, source, overwrite=overwrite)


def collect_episode_paths_with_externals(store: MemoryStore) -> Iterable[Path]:
    """Yield every ``*.jsonl`` under transcripts_dir for the dream pipeline."""
    return sorted(store.transcripts_dir.glob("*.jsonl"))
