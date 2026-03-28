from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN_SPEC_ROOT = REPO_ROOT / "openspec" / "changes" / "401-autodream-style-memory-subsystem"
CANONICAL_SCHEMA_ROOT = REPO_ROOT / "specs" / "401-autodream-style-memory-subsystem" / "schema"
SCHEMA_ROOT = Path(__file__).resolve().with_name("schema")
FIXTURE_ROOT = Path(__file__).resolve().with_name("fixtures")

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "use",
    "we",
    "with",
}
SEMANTIC_SYNONYMS = {
    "package": "dependency",
    "packages": "dependency",
    "dependency": "dependency",
    "dependencies": "dependency",
    "installer": "dependency",
    "manager": "dependency",
    "npm": "dependency",
    "pnpm": "dependency",
    "uv": "dependency",
    "workflow": "workflow",
    "process": "workflow",
    "procedure": "workflow",
    "steps": "workflow",
    "migrate": "migration",
    "migration": "migration",
    "migrations": "migration",
    "schema": "migration",
    "redis": "redis",
    "cache": "redis",
    "caching": "redis",
    "summary": "summary",
    "summaries": "summary",
    "concise": "brief",
    "brief": "brief",
    "pager": "pager",
    "paging": "pager",
    "bat": "pager",
    "ripgrep": "search",
    "search": "search",
    "find": "search",
}


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


def semantic_tokens(text: str) -> set[str]:
    normalized: set[str] = set()
    for token in tokenize(text):
        if token in STOPWORDS:
            continue
        normalized.add(SEMANTIC_SYNONYMS.get(token, token))
    return normalized


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


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json_dumps(data) + "\n")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_relative_to(path: Path, base: Path) -> None:
    path.resolve().relative_to(base.resolve())
