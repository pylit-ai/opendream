from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def default_reporting_agent() -> dict[str, Any]:
    return {
        "agent_id": "unknown",
        "agent_label": "Unknown",
        "model_id": "unknown",
        "model_version": "unknown",
    }


def normalize_reporting_agent(reporting_agent: dict[str, Any] | None = None) -> dict[str, Any]:
    agent = default_reporting_agent()
    if not reporting_agent:
        return agent
    agent_id = str(reporting_agent.get("agent_id") or "").strip()
    agent_label = str(reporting_agent.get("agent_label") or "").strip()
    if agent_id:
        agent["agent_id"] = agent_id
    if agent_label:
        agent["agent_label"] = agent_label
    elif agent_id:
        agent["agent_label"] = agent_id
    for key in ("runtime", "adapter_id", "model_id", "model_version", "genome_hash"):
        value = str(reporting_agent.get(key) or "").strip()
        if value:
            agent[key] = value
    return agent


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
    reporting_agent: dict[str, Any] = field(default_factory=default_reporting_agent)
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
    claim_class: str = "derived_abstraction"

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
    provenance_tier: str = "inferred"
    claim_class: str = "derived_abstraction"
    preconditions: list[str] = field(default_factory=list)
    recovery_steps: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    success_markers: list[str] = field(default_factory=list)
    lifecycle: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.workflow_steps:
            payload.pop("workflow_steps")
        for key in ("preconditions", "recovery_steps", "anti_patterns", "success_markers"):
            if not payload.get(key):
                payload.pop(key, None)
        if not payload.get("lifecycle"):
            payload.pop("lifecycle", None)
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
    reporting_agent: dict[str, Any] = field(default_factory=default_reporting_agent)
    profile: dict[str, Any] = field(default_factory=dict)
    selection: dict[str, Any] = field(default_factory=dict)
    context_pruning: dict[str, Any] = field(default_factory=dict)
    prompt_context_visibility: dict[str, Any] = field(default_factory=dict)
    injected_blocks: list[dict[str, Any]] = field(default_factory=list)
    selected_learned_context_items: list[dict[str, Any]] = field(default_factory=list)
    suppressed_learned_context_items: list[dict[str, Any]] = field(default_factory=list)

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


@dataclass(slots=True)
class LearnedContextRecord:
    record_id: str
    workspace_id: str
    source_event_ids: list[str]
    query_family_tags: list[str]
    summary: str
    provider_id: str
    model_id: str
    prompt_version: str
    created_at: str
    fresh_until: str
    confidence: float
    verifier_status: str
    status: str
    source_episode_ids: list[str] = field(default_factory=list)
    source_trace_ids: list[str] = field(default_factory=list)
    details: str = ""
    assumptions: str = ""
    conflict_state: str = "none"
    superseded_by: str | None = None
    harm_signals: list[str] = field(default_factory=list)
    promotion_target: str = "none"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.superseded_by is None:
            payload.pop("superseded_by")
        if not self.harm_signals:
            payload.pop("harm_signals")
        if not self.source_episode_ids:
            payload.pop("source_episode_ids")
        if not self.source_trace_ids:
            payload.pop("source_trace_ids")
        return payload


@dataclass(slots=True)
class QueryFamily:
    family_id: str
    title: str
    description: str
    examples: list[str]
    source_signals: list[str] = field(default_factory=list)
    predicted_frequency: float = 0.5
    predicted_value: float = 0.5
    freshness_window_hours: int = 168
    allowed_memory_types: list[str] = field(default_factory=list)
    success_metrics: list[str] = field(default_factory=list)
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.source_signals:
            payload.pop("source_signals")
        if not self.allowed_memory_types:
            payload.pop("allowed_memory_types")
        if not self.success_metrics:
            payload.pop("success_metrics")
        return payload


@dataclass(slots=True)
class ProviderEntry:
    provider_id: str
    transport: str
    model_id: str
    roles: list[str]
    context_window: int = 128000
    cost_hints: dict[str, Any] = field(default_factory=dict)
    rate_limit_hints: dict[str, Any] = field(default_factory=dict)
    supports_structured_output: bool = True
    supports_reasoning_effort: bool = False
    supports_tool_use: bool = False
    supports_local_offline_use: bool = False
    health_status: str = "unavailable"
    last_health_check_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.last_health_check_at is None:
            payload.pop("last_health_check_at")
        return payload


@dataclass(slots=True)
class SemanticDreamReport:
    run_id: str
    mode: str
    status: str
    started_at: str
    phases: list[str]
    trigger_class: str
    reason: str = ""
    ended_at: str = ""
    provider_id: str = ""
    model_id: str = ""
    execution_strategy: str = "deterministic"
    execution_owner: str = "opendream-local"
    auth_source: str = "none"
    trust_boundary: str = "no-model-call"
    query_families_considered: int = 0
    query_families_selected: int = 0
    proposals_generated: int = 0
    proposals_approved: int = 0
    proposals_rejected: int = 0
    learned_context_created: int = 0
    learned_context_superseded: int = 0
    promoted_record_ids: list[str] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    deterministic_summary: dict[str, Any] = field(default_factory=dict)
    semantic_summary: dict[str, Any] = field(default_factory=dict)
    verifier_summary: dict[str, Any] = field(default_factory=dict)
    harm_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.harm_signals:
            payload.pop("harm_signals")
        if not self.deterministic_summary:
            payload.pop("deterministic_summary")
        if not self.semantic_summary:
            payload.pop("semantic_summary")
        if not self.verifier_summary:
            payload.pop("verifier_summary")
        if not self.promoted_record_ids:
            payload.pop("promoted_record_ids")
        return payload


@dataclass(slots=True)
class BenchmarkRunReport:
    run_id: str
    benchmark_type: str
    mode: str
    status: str
    started_at: str
    scores: dict[str, Any] = field(default_factory=dict)
    competency_results: list[dict[str, Any]] = field(default_factory=list)
    ablation_tag: str = ""
    memory_hurt: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    token_cost: int = 0
    fixtures_used: list[str] = field(default_factory=list)
    ended_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.competency_results:
            payload.pop("competency_results")
        if not self.fixtures_used:
            payload.pop("fixtures_used")
        return payload


@dataclass(slots=True)
class RelationEdge:
    edge_id: str
    from_id: str
    to_id: str
    kind: str
    created_at: str
    reason: str = ""
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.evidence_ids:
            payload.pop("evidence_ids")
        if not self.reason:
            payload.pop("reason")
        return payload


@dataclass(slots=True)
class ClaimVerificationReport:
    report_id: str
    claim_id: str
    claim_class: str
    provenance_tier: str
    result: str
    checked_at: str
    verification_reads: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.verification_reads:
            payload.pop("verification_reads")
        if not self.reason:
            payload.pop("reason")
        return payload


@dataclass(slots=True)
class TranscriptProbeReport:
    run_id: str
    probes: list[str]
    hits: int
    windows_read: int
    escalations: int
    bytes_read: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.reasons:
            payload.pop("reasons")
        return payload


@dataclass(slots=True)
class ReconciliationReport:
    report_id: str
    workspace: str
    findings: list[str]
    actions: list[str]
    created_at: str
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MemoryExcellenceScorecard:
    scorecard_id: str
    scores: dict[str, Any]
    thresholds: dict[str, Any]
    passed: bool
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.artifacts:
            payload.pop("artifacts")
        return payload


@dataclass(slots=True)
class HarnessOptimizationReport:
    run_id: str
    status: str
    started_at: str
    search_space: dict[str, Any] = field(default_factory=dict)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    winning_variant_id: str = ""
    baseline_score: float = 0.0
    best_score: float = 0.0
    improvement_delta: float = 0.0
    iterations: int = 0
    duration_ms: int = 0
    ended_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AdvancedRuntimeReport:
    report_id: str
    generated_at: str
    modes: list[dict[str, Any]]
    memory_excellence_summary: dict[str, Any]
    docs_truthfulness: dict[str, Any]
    release_verdict: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.notes:
            payload.pop("notes")
        return payload
