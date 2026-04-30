from __future__ import annotations

import json
import re
from collections import deque
from datetime import timedelta
from pathlib import Path
from typing import Any

from .models import MemoryEvent
from .sessions import current_session_id
from .util import parse_timestamp, semantic_tokens, stable_id, to_iso

RELATIVE_DATE_PATTERNS = {
    r"\btoday\b": 0,
    r"\byesterday\b": -1,
    r"\btomorrow\b": 1,
}
MEMORY_WORTHY_MARKERS = (
    "prefer",
    "use ",
    "uses ",
    "required",
    "requires",
    "need ",
    "needs ",
    "workflow",
    "migration",
    "avoid",
    "failed",
    "remember",
)


def load_episode_rows(paths: list[Path], *, tail_limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        text = path.expanduser().read_text(encoding="utf-8").strip()
        if not text:
            continue
        if tail_limit is None:
            candidate_lines = [line for line in text.splitlines() if line.strip()]
        else:
            candidate_lines = list(deque((line for line in text.splitlines() if line.strip()), maxlen=tail_limit))
        for line in candidate_lines:
            payload = json.loads(line)
            if isinstance(payload, dict):
                payload.setdefault("source_path", str(path.expanduser()))
                rows.append(payload)
    rows.sort(key=lambda item: str(item.get("timestamp", "")))
    return rows


def latest_episode_timestamp(paths: list[Path]) -> str | None:
    rows = load_episode_rows(paths, tail_limit=1)
    if not rows:
        return None
    return max(str(row.get("timestamp") or "") for row in rows if row.get("timestamp")) or None


def normalize_relative_dates(text: str, reference_timestamp: str) -> str:
    normalized = text
    reference = parse_timestamp(reference_timestamp)
    for pattern, offset in RELATIVE_DATE_PATTERNS.items():
        replacement = reference + timedelta(days=offset)
        normalized = re.sub(pattern, replacement.strftime("%Y-%m-%d"), normalized, flags=re.IGNORECASE)
    return normalized


def infer_event_kind(text: str) -> tuple[str | None, list[str]]:
    lowered = text.lower()
    tags: list[str] = []
    if "prefer" in lowered:
        return ("preference_signal", tags)
    if "workflow" in lowered or "migration" in lowered or "steps" in lowered:
        tags.extend(["workflow:schema-migration", "success:true"])
        return ("workflow_step", tags)
    if "required" in lowered or "requires" in lowered or "need " in lowered or "needs " in lowered:
        return ("environment_requirement", tags)
    if "avoid" in lowered or "failed" in lowered or "failure" in lowered:
        return ("tool_failure", tags)
    if "remember" in lowered:
        return ("remember_request", tags)
    if "use " in lowered or "uses " in lowered:
        return ("project_decision", tags)
    return (None, tags)


def looks_memory_worthy(text: str, orientation_tokens: set[str]) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in MEMORY_WORTHY_MARKERS):
        return True
    return bool(semantic_tokens(text) & orientation_tokens)


def row_to_event(row: dict[str, Any], *, scope: str = "project") -> MemoryEvent | None:
    timestamp = str(row.get("timestamp") or "")
    content = str(row.get("text") or row.get("message") or row.get("content") or "").strip()
    if not timestamp or not content:
        return None
    normalized_content = normalize_relative_dates(content, timestamp)
    kind, tags = infer_event_kind(normalized_content)
    if kind is None:
        return None
    speaker = str(row.get("speaker") or row.get("role") or "transcript")
    message_ref = str(row.get("id") or stable_id("episode", timestamp, speaker, normalized_content))
    return MemoryEvent(
        event_id=stable_id("event", timestamp, speaker, normalized_content),
        session_id=(
            row.get("session_id")
            or current_session_id()
            or stable_id("session", row.get("session_id", "dream"), speaker)
        ),
        turn_id=stable_id("turn", timestamp, speaker, normalized_content[:32]),
        timestamp=to_iso(parse_timestamp(timestamp)),
        scope=scope,
        kind=kind,
        source={
            "channel": "system",
            "message_ref": message_ref,
            "file_refs": [str(row.get("source_path", ""))],
        },
        content=normalized_content,
        tags=[tag for tag in tags if tag],
    )
