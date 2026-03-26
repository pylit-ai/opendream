from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class MemoryEvent:
    event_id: str
    session_id: str
    turn_id: str
    timestamp: str
    scope: str
    kind: str
    source: dict[str, Any]
    content: str
    tags: list[str] = field(default_factory=list)
    confidence_hint: float | None = None
    sensitivity: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.confidence_hint is None:
            payload.pop("confidence_hint")
        if not self.tags:
            payload.pop("tags")
        if self.sensitivity == "normal":
            payload.pop("sensitivity")
        return payload


@dataclass(slots=True)
class MemoryCandidate:
    candidate_id: str
    derived_from_event_ids: list[str]
    type: str
    scope: str
    title: str
    summary: str
    body: str
    confidence: float
    salience: float
    status: str
    created_at: str
    origin_mode: str
    retrieval_boost: float = 0.0
    memory_refs: list[str] = field(default_factory=list)
    conflicts_with: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MemoryRecord:
    memory_id: str
    type: str
    scope: str
    title: str
    summary: str
    body: str
    status: str
    confidence: float
    salience: float
    source_event_ids: list[str]
    supersedes: list[str]
    conflicts_with: list[str]
    valid_from: str
    valid_to: str | None
    access_count: int
    last_accessed_at: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StartupIndexEntry:
    memory_id: str
    title: str
    type: str
    summary: str
    path: str
    priority: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConsolidationOperation:
    op_id: str
    run_id: str
    op: str
    target_id: str
    reason: str
    source_event_ids: list[str]
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
