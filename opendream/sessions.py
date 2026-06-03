"""Canonical session-id minter for OpenDream.

Provides a single source of truth for the current logical session id so that
all emit and retrieval paths share one id per agent span instead of each
minting their own.
"""
from __future__ import annotations

import contextvars
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .storage import MemoryStore

_SESSION_ID_VAR: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_SESSION_ID_VAR", default=None
)


def _workspace_token_path(store: MemoryStore) -> Path:
    return store.memory_root / ".active_session"


def current_session_id(store: MemoryStore | None = None) -> str | None:
    """Return the current session id, or None if not set.

    Checks the contextvar first; falls back to the workspace token file when a
    store token has been written by a parent span.  All I/O is guarded so a
    corrupt or missing file never raises.
    """
    val = _SESSION_ID_VAR.get()
    if val is not None:
        return val
    if store is not None:
        try:
            session_id = _workspace_token_path(store).read_text(encoding="utf-8").strip()
            return session_id or None
        except Exception:
            return None
    return None


def set_session_id(value: str, *, store: MemoryStore | None = None) -> None:
    """Set the current session id in the contextvar and optionally persist it."""
    _SESSION_ID_VAR.set(value)
    if store is not None:
        try:
            token_path = _workspace_token_path(store)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=".active_session.tmp-", dir=token_path.parent
            )
            temp_path = Path(temp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(value)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(temp_path, token_path)
            finally:
                temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def clear_session_id(*, store: MemoryStore | None = None) -> None:
    """Clear the contextvar and optionally remove the token file."""
    _SESSION_ID_VAR.set(None)
    if store is not None:
        try:
            token_path = _workspace_token_path(store)
            token_path.unlink(missing_ok=True)
        except Exception:
            pass


def cleanup_orphans(
    store: MemoryStore,
    *,
    orphans: bool = False,
    zero_events: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Remove orphan event records and/or zero-event session entities.

    Orphan events: event records whose session_id does not resolve to any
    known session (from context assemblies or the saved observability index).

    Zero-event sessions: known sessions with no events in the live log.

    Uses atomic file writes (tempfile + rename) when rewriting the events log.
    Returns a summary dict with removed counts and sample ids.
    """
    # Build known_session_ids from contexts and saved index (same logic as
    # _session_diagnostics) so orphan detection is consistent.
    contexts = store.load_context_assemblies()
    context_sessions: set[str] = {
        str(ctx.get("session_id") or "")
        for ctx in contexts
        if ctx.get("session_id")
    }
    index_sessions: set[str] = set()
    entity_event_counts: dict[str, int] = {}
    if store.observability_index_path.exists():
        try:
            saved = store.load_observability_index()
            for s in (saved.get("entities") or {}).get("sessions") or []:
                sid = str(s.get("session_id") or "")
                if sid:
                    index_sessions.add(sid)
                    entity_event_counts[sid] = int(s.get("event_count") or 0)
        except Exception:
            pass
    known_session_ids: set[str] = context_sessions | index_sessions

    removed_event_count = 0
    removed_session_count = 0
    samples: list[str] = []

    # If there are no known sessions from any authoritative source (no index, no
    # contexts), skip orphan removal to avoid deleting valid events on a fresh or
    # uninitialised workspace.
    has_authoritative_source = bool(context_sessions or index_sessions)

    if orphans and not has_authoritative_source:
        # Nothing to cross-reference against; skip silently.
        pass
    elif orphans:
        # Rewrite each events JSONL file, dropping orphan records
        events_dir = store.events_dir
        if events_dir.exists():
            for path in sorted(events_dir.glob("*.jsonl")):
                kept: list[dict[str, Any]] = []
                removed_in_file = 0
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        kept.append({})  # preserve corrupt lines as-is
                        continue
                    sid = str(event.get("session_id") or "")
                    if sid and sid not in known_session_ids:
                        removed_in_file += 1
                        if len(samples) < 25:
                            samples.append(str(event.get("event_id", sid)))
                    else:
                        kept.append(event)
                if removed_in_file and not dry_run:
                    new_text = (
                        "\n".join(json.dumps(r, sort_keys=True) for r in kept if r) + "\n"
                        if kept
                        else ""
                    )
                    fd, temp_name = tempfile.mkstemp(
                        prefix=f".{path.name}.tmp-", dir=path.parent
                    )
                    temp_path = Path(temp_name)
                    try:
                        with os.fdopen(fd, "w", encoding="utf-8") as fh:
                            fh.write(new_text)
                            fh.flush()
                            os.fsync(fh.fileno())
                        os.replace(temp_path, path)
                    finally:
                        temp_path.unlink(missing_ok=True)
                removed_event_count += removed_in_file

    if zero_events:
        # Zero-event sessions: known sessions with no events in the live log.
        # Group live events by session_id to detect which sessions have 0 events.
        live_events = store.load_events()
        live_sids: set[str] = {
            str(e.get("session_id") or "")
            for e in live_events
            if e.get("session_id")
        }
        zero_sids = [sid for sid in known_session_ids if sid not in live_sids]
        removed_session_count = len(zero_sids)
        if len(samples) < 25:
            samples.extend(zero_sids[: 25 - len(samples)])

    return {
        "removed_event_count": removed_event_count,
        "removed_session_count": removed_session_count,
        "dry_run": dry_run,
        "samples": samples,
    }
