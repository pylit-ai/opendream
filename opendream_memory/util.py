from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN_SPEC_ROOT = REPO_ROOT / "openspec" / "changes" / "401-autodream-style-memory-subsystem"
SCHEMA_ROOT = OPEN_SPEC_ROOT / "schema"

TOKEN_RE = re.compile(r"[a-z0-9]+")


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return utc_now()
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)


def stable_id(prefix: str, *parts: object) -> str:
    payload = "::".join(str(part) for part in parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned or "item"


def summarize(text: str, max_chars: int = 140) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def tokenize(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if len(token) > 1}


def parse_tags(tags: list[str] | None) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for tag in tags or []:
        if ":" in tag:
            key, value = tag.split(":", 1)
        else:
            key, value = tag, ""
        parsed.setdefault(key, []).append(value)
    return parsed


def first_tag(tags: list[str] | None, key: str) -> str | None:
    values = parse_tags(tags).get(key)
    return values[0] if values else None


def json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(data) + "\n", encoding="utf-8")


def ensure_relative_to(path: Path, base: Path) -> None:
    path.resolve().relative_to(base.resolve())
