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
    workflow_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.workflow_steps:
            payload.pop("workflow_steps")
        return payload


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
    workflow_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.workflow_steps:
            payload.pop("workflow_steps")
        return payload


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


@dataclass(slots=True)
class ContextAssembly:
    context_id: str
    session_id: str
    turn_id: str
    retrieval_run_id: str
    startup_index_snapshot: list[dict[str, Any]]
    selected_memory_ids: list[str]
    omitted_memory_ids: list[str]
    omission_reasons: list[dict[str, Any]]
    assembled_text: str
    character_count: int
    token_estimate: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ObservabilityConsolidationOp:
    id: str
    run_id: str
    phase: str
    op_type: str
    target_memory_id: str | None
    source_candidate_ids: list[str]
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]
    reason: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Annotation:
    id: str
    object_type: str
    object_id: str
    actor: str
    label: str
    score: float | None
    note: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.score is None:
            payload.pop("score")
        return payload


@dataclass(slots=True)
class ReviewDecision:
    id: str
    queue_item_type: str
    queue_item_id: str
    action: str
    rationale: str
    actor: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PhaseTrace:
    id: str
    run_id: str
    phase: str
    started_at: str
    ended_at: str
    inputs_count: int
    outputs_count: int
    warning_count: int
    error_count: int
    files_consulted: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.files_consulted:
            payload.pop("files_consulted")
        return payload


@dataclass(slots=True)
class AutomationJob:
    version: int
    job_id: str
    title: str
    description: str
    skill_ref: str
    enabled: bool
    trigger: dict[str, Any]
    input_selectors: dict[str, Any]
    output: dict[str, Any]
    merge_policy: dict[str, Any]
    decay_policy: dict[str, Any]
    review_policy: dict[str, Any]
    security_policy: dict[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutomationRecord:
    version: int
    record_id: str
    job_id: str
    record_type: str
    title: str
    summary: str
    status: str
    confidence: float
    priority: float
    dedupe_key: str
    source_memory_ids: list[str]
    source_titles: list[str]
    missed_runs: int
    created_at: str
    updated_at: str
    last_seen_at: str
    stale_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.stale_at is None:
            payload.pop("stale_at")
        return payload
